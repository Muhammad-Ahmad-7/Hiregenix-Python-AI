
from config.db import question_result_collection, interview_collection
from bson import ObjectId
import numpy as np
from datetime import datetime
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Optional
from prompts.llm_eval import INTERVIEW_EVALUATION_PROMPT
from langchain.chat_models.base import init_chat_model
from config.env import OPENAI_API_KEY
from enum import Enum
from pymongo import ReturnDocument

from utils.llm_call import get_llm_model


from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ValidationError

from langchain.output_parsers import PydanticOutputParser
from langchain.output_parsers import OutputFixingParser


# =========================
# ENUMS
# =========================

class AnswerQualityEnum(str, Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    AVERAGE = "Average"
    POOR = "Poor"


class GrammarQualityEnum(str, Enum):
    POOR = "Poor"
    BELOW_AVERAGE = "Below Average"
    AVERAGE = "Average"
    GOOD = "Good"
    EXCELLENT = "Excellent"


class SpeechFlowEnum(str, Enum):
    DISJOINTED = "Disjointed"
    SOMEWHAT_DISJOINTED = "Somewhat Disjointed"
    ACCEPTABLE = "Acceptable"
    SMOOTH = "Smooth"


class PaceAssessmentEnum(str, Enum):
    VERY_SLOW = "Very Slow"
    SLOW = "Slow"
    MODERATE = "Moderate"
    FAST = "Fast"
    VERY_FAST = "Very Fast"


# =========================
# MODELS
# =========================

class ScoreBreakdown(BaseModel):
    contentScore: int = Field(..., ge=0, le=100)
    communicationScore: int = Field(..., ge=0, le=100)
    fluencyScore: int = Field(..., ge=0, le=100)
    confidenceScore: int = Field(..., ge=0, le=100)
    overallScore: int = Field(..., ge=0, le=100)


class FluencyAssessment(BaseModel):
    grammarQuality: GrammarQualityEnum
    speechFlow: SpeechFlowEnum
    paceAssessment: PaceAssessmentEnum
    detectedIssues: List[str] = Field(default_factory=list)

    # 🔥 SELF-HEALING NORMALIZER
    @field_validator("paceAssessment", mode="before")
    @classmethod
    def normalize_pace(cls, value):
        if not value:
            return "Moderate"

        v = str(value).lower()

        if "very slow" in v:
            return "Very Slow"
        if "slow" in v:
            return "Slow"
        if "very fast" in v:
            return "Very Fast"
        if "fast" in v:
            return "Fast"
        if "moderate" in v:
            return "Moderate"

        return "Moderate"


class EvaluationInsights(BaseModel):
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    missingConcepts: List[str] = Field(default_factory=list)
    improvementSuggestions: List[str] = Field(default_factory=list)


class IntegrityAssessment(BaseModel):
    integrityConcern: bool = False
    integrityNotes: Optional[str] = None


class InterviewEvaluation(BaseModel):
    scores: ScoreBreakdown
    fluencyAssessment: FluencyAssessment
    insights: EvaluationInsights
    answerQuality: AnswerQualityEnum
    integrity: IntegrityAssessment
    shortSummary: str


# =========================
# LANGCHAIN PARSERS
# =========================

parser = PydanticOutputParser(pydantic_object=InterviewEvaluation)

fixing_parser = OutputFixingParser.from_llm(
    parser=parser,
    llm=get_llm_model("grok/gpt-oss-20b")  # inject your LLM here when initializing
)


# =========================
# SAFE + SELF-HEALING PARSER
# =========================

def cheap_fix_json(output: str) -> str:
    """
    Lightweight pre-fix before hitting LLM retry.
    """
    try:
        import json
        data = json.loads(output)

        # normalize paceAssessment if present
        pace = data.get("fluencyAssessment", {}).get("paceAssessment", "")
        if isinstance(pace, str) and "moderate" in pace.lower():
            data["fluencyAssessment"]["paceAssessment"] = "Moderate"

        return json.dumps(data)

    except Exception:
        return output


def robust_parse(llm, output: str, max_retries: int = 2):
    """
    Full self-healing pipeline:
    1. Cheap fix
    2. Direct parse
    3. LangChain fix parser
    4. LLM repair retry
    """

    output = cheap_fix_json(output)

    # Step 1: direct parse
    try:
        return parser.parse(output)
    except ValidationError:
        pass

    # Step 2: LangChain auto-fix
    try:
        return fixing_parser.parse(output)
    except Exception:
        pass

    # Step 3: controlled LLM repair loop
    for _ in range(max_retries):
        repair_prompt = f"""
Fix this JSON to match schema EXACTLY.
- Keep meaning
- Fix enum values strictly
- No extra text

JSON:
{output}
"""

        output = llm.invoke(repair_prompt).content

        try:
            return parser.parse(output)
        except ValidationError:
            continue

    raise ValueError("Failed to parse even after self-healing attempts")


# initialize model (example — adapt to your stack)
model = get_llm_model("grok/gpt-oss-120b")

DIMENSION_WEIGHTS = {
    "contentScore": 0.50,
    "communicationScore": 0.20,
    "fluencyScore": 0.15,
    "confidenceScore": 0.15,
}

TAB_SWITCH_CONFIDENCE_CAP = 40
TAB_SWITCH_OVERALL_CAP = 50
INTEGRITY_QUESTION_OVERALL_CAP = 60


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
        return 0
    return max(0, min(100, int(round(float(value)))))


def compute_weighted_overall_score(scores):
    weighted_total = 0.0
    weighted_denominator = 0.0

    for field, weight in DIMENSION_WEIGHTS.items():
        value = scores.get(field)
        if isinstance(value, (int, float)):
            weighted_total += float(value) * weight
            weighted_denominator += weight

    return int(round(weighted_total / weighted_denominator)) if weighted_denominator else 0


def apply_numeric_scoring_rules(evaluation, tab_switches=0):
    scores = evaluation.setdefault("scores", {})
    for field in DIMENSION_WEIGHTS:
        scores[field] = clamp_score(scores.get(field))

    tab_switch_count = int(tab_switches or 0)
    integrity = evaluation.setdefault("integrity", {})

    if tab_switch_count >= 1:
        scores["confidenceScore"] = min(scores["confidenceScore"], TAB_SWITCH_CONFIDENCE_CAP)
        integrity["integrityConcern"] = True
        tab_note = f"Tab switching detected ({tab_switch_count} time(s)), which is treated as a strong integrity concern."
        existing_notes = integrity.get("integrityNotes")
        integrity["integrityNotes"] = f"{existing_notes} {tab_note}".strip() if existing_notes else tab_note
        if evaluation.get("answerQuality") == AnswerQualityEnum.EXCELLENT.value:
            evaluation["answerQuality"] = AnswerQualityEnum.GOOD.value

    scores["overallScore"] = compute_weighted_overall_score(scores)

    if is_integrity_flagged(integrity.get("integrityConcern")):
        scores["overallScore"] = min(scores["overallScore"], INTEGRITY_QUESTION_OVERALL_CAP)

    if tab_switch_count >= 1:
        scores["overallScore"] = min(scores["overallScore"], TAB_SWITCH_OVERALL_CAP)

    return evaluation


def llm_eval_pipeline(question_result_id: str):
    try:
        question_result = question_result_collection.find_one({"_id": ObjectId(question_result_id)})
        print(f" 🔍 Fetched Question Result {question_result_id} from DB: {question_result}")

        if not question_result:
            print("❌ Question Result not found in DB")
            return False
        print(f"✅ Question Result found in DB: {question_result}")
        
        prompt_template = ChatPromptTemplate.from_messages([
        ("system", INTERVIEW_EVALUATION_PROMPT),
        ("human", "Please perform the interview evaluation for me : {question_text} {transcript_text} {audio_analysis} {video_analysis} {verification_summary} {tab_switches}"),
        ])

        prompt = prompt_template.format(
            question_text=question_result['questionText'],
            transcript_text=question_result['sttData']['text'],
            audio_analysis=question_result['audioAnalysis'],
            video_analysis=question_result['videoAnalysis'],
            verification_summary=question_result.get("verificationSummary"),
            tab_switches=question_result['numberOfTabSwitch'],
            format_instructions=parser.get_format_instructions()
        )
        
        result = model.invoke(prompt)
        parsed_output = parser.parse(result.content)
        final_result = parsed_output.model_dump()
        final_result = apply_numeric_scoring_rules(
            final_result,
            question_result.get('numberOfTabSwitch', 0)
        )
        
        # DB question result document updated with the llm evaluation result and stages.llmEvaluated = true, stages.done = true and status = completed
        question_result_collection.update_one(
            {"_id": ObjectId(question_result_id)},
            {"$set": {
                "lLMAnalysis": final_result,
                "stages.llmEvaluated": True,
                "stages.done": True,
                "status": "DONE",
                "updatedAt": datetime.now(),
            }},
        )
        print(f"✅ Question Result {question_result_id} updated with llm analysis")
        return True

    except Exception as e:
        print(f"❌ Error processing question result {question_result_id}: {e}")
        return False
