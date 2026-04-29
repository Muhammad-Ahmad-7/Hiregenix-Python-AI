
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
model = get_llm_model("grok/llama-70b")
def final_interview_pipeline(interview_id: str):
    try:
        interview_doc = interview_collection.find_one({"_id": ObjectId(interview_id)})
        print(f" 🔍 Fetched interview document {interview_collection} from DB: {interview_doc}")

        if not interview_doc:
            print("❌ interview document not found in DB")
            return False
        # print(f"✅ interview document found in DB: {interview_doc}")

        question_docs = question_result_collection.find({"interviewId": ObjectId(interview_id)})
        
        
        # for doc in question_docs:
        #     print(doc['lLMAnalysis']['scores'])
        #     print(doc['lLMAnalysis']['insights'])
        #     print(doc['lLMAnalysis']['shortSummary'])
        #     print(doc['questionText'])
            # break
        
        input_data = []
        for doc in question_docs:
            if doc['lLMAnalysis']:
                input_data.append({
                    "questionId": doc['_id'],
                    "scores": doc['lLMAnalysis']['scores'] if doc['lLMAnalysis']['scores'] else {},
                    "fluencyAssessment": doc['lLMAnalysis']['fluencyAssessment'] if doc['lLMAnalysis']['fluencyAssessment'] else {},
                    "insights": doc['lLMAnalysis']['insights'] if doc['lLMAnalysis']['insights'] else {},
                    "shortSummary": doc['lLMAnalysis']['shortSummary'] if doc['lLMAnalysis']['shortSummary'] else {},
                    "questionText": doc['questionText'] if doc['questionText'] else {},
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
        
        print(f"This is the final result of full interview got from llm {final_result}")
        
        # Create report document with the final_result got from the llm
        
        now = datetime.now()

        report_doc = {
            "interviewId": ObjectId(interview_id),
            "contentScore": final_result['overallScores']['contentScore'],
            "fluencyScore": final_result['overallScores']['fluencyScore'],
            "communicationScore": final_result['overallScores']['communicationScore'],
            "confidenceScore": final_result['overallScores']['confidenceScore'],
            "overallScore": final_result['overallScores']['overallScore'],
            "overallAnswerQuality": final_result['overallAnswerQuality'],
            "overallInterviewScore": final_result['overallInterviewScore'],
            "topStrengths": final_result['topStrengths'],
            "topWeaknesses": final_result['topWeaknesses'],
            "commonMissingConcepts": final_result['commonMissingConcepts'],
            "overallImprovementSuggestions": final_result['overallImprovementSuggestions'],
            "integrityConcern": final_result['integrity']['integrityConcern'],
            "integrityNotes": final_result['integrity']['integrityNotes'],
            "interviewSummary": final_result['interviewSummary'],
        }

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