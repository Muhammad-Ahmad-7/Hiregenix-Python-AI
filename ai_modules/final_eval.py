
from config.db import interview_collection, question_result_collection, report_collection
from bson import ObjectId
import numpy as np
from datetime import datetime
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Optional
from prompts.final_interview_eval import FINAL_INTERVIEW_AGGREGATION_PROMPT
from utils.llm_call import get_llm_model

class FluencyAssessment(BaseModel):
    grammarQuality: Optional[str] = None
    speechFlow: Optional[str] = None
    paceAssessment: Optional[str] = None
    detectedIssues: List[str] = []

class IntegrityAssessment(BaseModel):
    integrityConcern: bool = False
    integrityNotes: Optional[str] = None

class FinalInterviewScores(BaseModel):
    contentScore: int = Field(..., ge=0, le=100)
    communicationScore: int = Field(..., ge=0, le=100)
    fluencyScore: int = Field(..., ge=0, le=100)
    confidenceScore: int = Field(..., ge=0, le=100)
    overallScore: int = Field(..., ge=0, le=100)

class FinalInterviewReport(BaseModel):
    overallScores: FinalInterviewScores
    overallAnswerQuality: str  # Excellent, Good, Average, Poor
    overallInterviewScore: int = Field(..., ge=0, le=100)
    topStrengths: List[str] = []
    topWeaknesses: List[str] = []
    commonMissingConcepts: List[str] = []
    overallImprovementSuggestions: List[str] = []
    integrity: IntegrityAssessment
    interviewSummary: str

parser = PydanticOutputParser(pydantic_object=FinalInterviewReport)


# initialize model (example — adapt to your stack)
model = get_llm_model("gemini/gemini-2.5-flash")


DIMENSION_WEIGHTS = {
    "contentScore": 0.50,
    "communicationScore": 0.20,
    "fluencyScore": 0.15,
    "confidenceScore": 0.15,
}

INTEGRITY_SCORE_CAP = 60
TAB_SWITCH_CONFIDENCE_CAP = 40
TAB_SWITCH_OVERALL_CAP = 50


def is_integrity_flagged(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value > 0
    value_text = str(value).strip().lower()
    return value_text in {"yes", "true", "1", "flagged", "concern", "high", "medium"}


def clamp_score(value):
    if not isinstance(value, (int, float)):
        return None
    return max(0, min(100, int(round(float(value)))))


def compute_weighted_overall_score(scores):
    weighted_total = 0.0
    weighted_denominator = 0.0

    for field, weight in DIMENSION_WEIGHTS.items():
        value = scores.get(field)
        if isinstance(value, (int, float)):
            weighted_total += float(value) * weight
            weighted_denominator += weight

    return int(round(weighted_total / weighted_denominator)) if weighted_denominator > 0 else None


def get_tab_switch_count(doc):
    return int(doc.get("numberOfTabSwitch") or 0)


def normalize_question_scores(doc):
    analysis = doc.get("lLMAnalysis") or {}
    raw_scores = analysis.get("scores") or {}
    scores = {}

    for field in DIMENSION_WEIGHTS:
        score = clamp_score(raw_scores.get(field))
        if score is not None:
            scores[field] = score

    tab_switch_count = get_tab_switch_count(doc)
    if tab_switch_count >= 1 and "confidenceScore" in scores:
        scores["confidenceScore"] = min(scores["confidenceScore"], TAB_SWITCH_CONFIDENCE_CAP)

    overall_score = compute_weighted_overall_score(scores)
    if overall_score is not None:
        if is_integrity_flagged((analysis.get("integrity") or {}).get("integrityConcern")):
            overall_score = min(overall_score, INTEGRITY_SCORE_CAP)
        if tab_switch_count >= 1:
            overall_score = min(overall_score, TAB_SWITCH_OVERALL_CAP)
        scores["overallScore"] = overall_score

    return scores


def aggregate_scores_from_questions(question_docs):
    score_fields = ["contentScore", "communicationScore", "fluencyScore", "confidenceScore", "overallScore"]
    totals = {field: 0.0 for field in score_fields}
    counts = {field: 0 for field in score_fields}

    for doc in question_docs:
        scores = normalize_question_scores(doc)
        for field in score_fields:
            value = scores.get(field)
            if isinstance(value, (int, float)):
                totals[field] += float(value)
                counts[field] += 1

    averages = {}
    for field in score_fields:
        if counts[field] > 0:
            averages[field] = int(round(totals[field] / counts[field]))

    return averages


def has_interview_integrity_concern(final_result, question_docs):
    if is_integrity_flagged(final_result.get("integrity", {}).get("integrityConcern")):
        return True

    for doc in question_docs:
        if get_tab_switch_count(doc) >= 1:
            return True
        analysis = doc.get("lLMAnalysis") or {}
        if is_integrity_flagged((analysis.get("integrity") or {}).get("integrityConcern")):
            return True

    return False


def build_integrity_notes(final_result, question_docs):
    notes = []
    final_notes = final_result.get("integrity", {}).get("integrityNotes")
    if final_notes:
        notes.append(str(final_notes))

    for doc in question_docs:
        tab_switch_count = get_tab_switch_count(doc)
        if tab_switch_count >= 1:
            notes.append(
                f"Question {doc.get('_id')} had {tab_switch_count} tab switch(es), which is treated as a strong integrity concern."
            )

        analysis = doc.get("lLMAnalysis") or {}
        integrity = analysis.get("integrity") or {}
        question_notes = integrity.get("integrityNotes")
        if is_integrity_flagged(integrity.get("integrityConcern")) and question_notes:
            notes.append(str(question_notes))

    deduped_notes = list(dict.fromkeys(notes))
    return " ".join(deduped_notes) if deduped_notes else None

def final_interview_pipeline(interview_id: str):
    try:
        interview_doc = interview_collection.find_one({"_id": ObjectId(interview_id)})
        print(f" 🔍 Fetched interview document {interview_collection} from DB: {interview_doc}")

        if not interview_doc:
            print("❌ interview document not found in DB")
            return False
        # print(f"✅ interview document found in DB: {interview_doc}")

        question_docs = list(question_result_collection.find({"interviewId": ObjectId(interview_id)}))
        
        
        # for doc in question_docs:
        #     print(doc['lLMAnalysis']['scores'])
        #     print(doc['lLMAnalysis']['insights'])
        #     print(doc['lLMAnalysis']['shortSummary'])
        #     print(doc['questionText'])
            # break
        
        input_data = []
        for doc in question_docs:
            if doc.get('lLMAnalysis'):
                normalized_scores = normalize_question_scores(doc)
                input_data.append({
                    "questionId": doc['_id'],
                    "scores": normalized_scores,
                    "fluencyAssessment": doc['lLMAnalysis'].get('fluencyAssessment') or {},
                    "insights": doc['lLMAnalysis'].get('insights') or {},
                    "answerQuality": doc['lLMAnalysis'].get("answerQuality"),
                    "integrity": doc['lLMAnalysis'].get("integrity"),
                    "shortSummary": doc['lLMAnalysis'].get('shortSummary') or {},
                    "questionText": doc.get('questionText') or {},
                    "tabSwitches": get_tab_switch_count(doc),
                })

        print("Final input data passing to llm for final interview evaluation", input_data)
        
        prompt_template = ChatPromptTemplate.from_messages([
        ("system", FINAL_INTERVIEW_AGGREGATION_PROMPT),
        ("human", "Please perform the final interview evaluation for the data of each questions provided to you : {questions_summary}"),
        ])

        prompt = prompt_template.format(
            questions_summary=input_data,
            format_instructions=parser.get_format_instructions()
        )
        
        result = model.invoke(prompt)
        parsed_output = parser.parse(result.content)
        final_result = parsed_output.model_dump()

        # Compute aggregated interview scores from per-question LLM scores.
        aggregated_scores = aggregate_scores_from_questions(question_docs)
        computed_overall_scores = {
            "contentScore": aggregated_scores.get("contentScore", final_result["overallScores"]["contentScore"]),
            "communicationScore": aggregated_scores.get("communicationScore", final_result["overallScores"]["communicationScore"]),
            "fluencyScore": aggregated_scores.get("fluencyScore", final_result["overallScores"]["fluencyScore"]),
            "confidenceScore": aggregated_scores.get("confidenceScore", final_result["overallScores"]["confidenceScore"]),
            "overallScore": aggregated_scores.get("overallScore")
        }

        computed_overall_interview_score = compute_weighted_overall_score(computed_overall_scores)
        if computed_overall_interview_score is None:
            computed_overall_interview_score = final_result["overallInterviewScore"]

        if computed_overall_scores["overallScore"] is None:
            computed_overall_scores["overallScore"] = computed_overall_interview_score

        integrity_flagged = has_interview_integrity_concern(final_result, question_docs)
        if integrity_flagged:
            computed_overall_interview_score = min(computed_overall_interview_score, INTEGRITY_SCORE_CAP)
        computed_overall_scores["overallScore"] = computed_overall_interview_score

        overall_answer_quality = final_result['overallAnswerQuality']
        if integrity_flagged and overall_answer_quality == "Excellent":
            overall_answer_quality = "Good"

        integrity_notes = build_integrity_notes(final_result, question_docs)
        
        print(f"This is the final result of full interview got from llm {final_result}")
        
        # Create report document with the final_result got from the llm
        
        now = datetime.now()

        report_doc = {
            "interviewId": ObjectId(interview_id),
            "contentScore": computed_overall_scores["contentScore"],
            "fluencyScore": computed_overall_scores["fluencyScore"],
            "communicationScore": computed_overall_scores["communicationScore"],
            "confidenceScore": computed_overall_scores["confidenceScore"],
            "overallScore": computed_overall_scores["overallScore"],
            "overallAnswerQuality": overall_answer_quality,
            "overallInterviewScore": computed_overall_interview_score,
            "topStrengths": final_result['topStrengths'],
            "topWeaknesses": final_result['topWeaknesses'],
            "commonMissingConcepts": final_result['commonMissingConcepts'],
            "overallImprovementSuggestions": final_result['overallImprovementSuggestions'],
            "integrityConcern": integrity_flagged,
            "integrityNotes": integrity_notes,
            "interviewSummary": final_result['interviewSummary'],
        }
        
        print(f"Final report document to be inserted/updated in DB: {report_doc}")

        result = report_collection.update_one(
            {"interviewId": ObjectId(interview_id)},
            {
                "$set": {
                    **report_doc,
                    "updatedAt": now
                },
                "$setOnInsert": {
                    "createdAt": now
                }
            },
            upsert=True
        )

        if result.upserted_id:
            print(f"✅ Report created: {result.upserted_id}")
            return result.upserted_id
        else:
            print("♻️ Report updated (no new insert)")
            return interview_id

    except Exception as e:
        print(f"❌ Error processing final interview evaluation {interview_id}: {e}")
        return False
