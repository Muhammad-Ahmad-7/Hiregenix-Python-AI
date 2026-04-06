
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
    detectedIssues: List[str] = []


class EvaluationInsights(BaseModel):
    strengths: List[str] = []
    weaknesses: List[str] = []
    missingConcepts: List[str] = []
    improvementSuggestions: List[str] = []


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


parser = PydanticOutputParser(pydantic_object=InterviewEvaluation)


# initialize model (example — adapt to your stack)
model = init_chat_model(model_provider='google_genai', model='gemini-2.5-flash', api_key=OPENAI_API_KEY)


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
        ("human", "Please perform the interview evaluation for me : {question_text} {transcript_text} {audio_analysis} {video_analysis}"),
        ])

        prompt = prompt_template.format(
            question_text=question_result['questionText'],
            transcript_text=question_result['sttData']['text'],
            audio_analysis=question_result['audioAnalysis'],
            video_analysis=question_result['videoAnalysis'],
            format_instructions=parser.get_format_instructions()
        )
        
        result = model.invoke(prompt)
        parsed_output = parser.parse(result.content)
        final_result = parsed_output.model_dump()
        
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