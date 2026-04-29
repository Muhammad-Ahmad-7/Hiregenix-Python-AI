from langchain_community.document_loaders import PyPDFLoader
from langchain.chat_models.base import init_chat_model
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Optional, List
from pydantic import BaseModel
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from config.env import OPENAI_API_KEY
from prompts.resume_parser import RESUME_PROMPT
from config.db import resume_collection, candidate_collection
from models.resume import ResumeModel, ParsedDataModel, ExperienceModel, EducationModel, ProjectModel, CertificationModel
from datetime import datetime
from bson import ObjectId

from utils.llm_call import get_llm_model

# initialize model (example — adapt to your stack)
# model = init_chat_model(model_provider='google_genai', model='gemini-2.5-flash', api_key=OPENAI_API_KEY)

model = get_llm_model("grok/gpt-oss-20b")  # Replace with your actual model initialization function

class StateSchema(TypedDict):
    resume_url: str
    candidate_id: str
    resume_text: str
    parsed_resume: dict

class Experience(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    description: Optional[str] = None

class Education(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    startYear: Optional[str] = None
    endYear: Optional[str] = None

class Project(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    link: Optional[str] = None
    technologies: List[str] = []

class Certification(BaseModel):
    name: Optional[str] = None
    issuer: Optional[str] = None
    year: Optional[str] = None

class ParsedResume(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedIn: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = []
    experience: List[Experience] = []
    education: List[Education] = []
    projects: List[Project] = []
    certifications: List[Certification] = []
    aiScore: float = 0.0
    aiSuggestions: List[str] = []

parser = PydanticOutputParser(pydantic_object=ParsedResume)

def pdf_loader(state: StateSchema) -> StateSchema:
    url = state['resume_url']
    loader = PyPDFLoader(url)
    documents = loader.load()
    full_text = "\n".join([doc.page_content for doc in documents])
    state['resume_text'] = full_text
    print("PDF LOADED", state['resume_text'])
    return state

def resume_parser(state: StateSchema) -> StateSchema:
    prompt_template = ChatPromptTemplate.from_messages([
    ("system", RESUME_PROMPT),
    ("human", "Extract the information from this resume text : {resume_text}"),
    ])

    prompt = prompt_template.format(
        resume_text=state['resume_text'],
        format_instructions=parser.get_format_instructions()
    )
    result = model.invoke(prompt)
    parsed_output = parser.parse(result.content)
    state['parsed_resume'] = parsed_output.model_dump()
    print("RESUME PARSED ", state['parsed_resume'])
    return state



def store_parsed_data(state: StateSchema) -> StateSchema:
    current_time = datetime.now()
    data = state['parsed_resume']
    
    resumeData = ResumeModel(
        aiScore=data.get('aiScore'),
        aiSuggestions=data.get('aiSuggestions'),  # Now handled by validator
        candidateId=ObjectId(state['candidate_id']),
        fileUrl=state['resume_url'],
        parsedData=ParsedDataModel(
            name=data.get('name'), 
            email=data.get('email'), 
            phone=data.get('phone'),
            linkedin=data.get('linkedIn'),
            github=data.get('github'), 
            portfolio=data.get('portfolio'),
            summary=data.get('summary'), 
            skills=data.get('skills'),  # Now handled by validator
            certifications=data.get('certifications'),  # Now handled by validator
            projects=data.get('projects'),  # Now handled by validator
            education=data.get('education'),  # Now handled by validator
            experience=data.get('experience')  # Now handled by validator
        ),
        createdAt=current_time,
        updatedAt=current_time
    )
    
    print("RESUME DATA:", resumeData)
    
    # Convert to dict, ensuring datetime values are preserved
    resume_dict = resumeData.model_dump(by_alias=True, exclude_unset=False, exclude_none=True)
    
    # Double-check datetime fields are set properly
    resume_dict['createdAt'] = current_time
    resume_dict['updatedAt'] = current_time
    
    print("RESUME DICT BEFORE INSERT:", resume_dict)
    
    result = resume_collection.insert_one(resume_dict)
    print(f"STORING PARSED DATA COMPLETED - Inserted ID: {result.inserted_id}")
    
    candidate_collection.update_one({"_id": ObjectId(state['candidate_id'])}, {"$set": {"resumeId": result.inserted_id}})
    print(f"UPDATED CANDIDATE {state['candidate_id']} WITH RESUME ID {result.inserted_id}")
    
    return state

# Define the state graph

def get_resume_parsing_graph() -> StateGraph[StateSchema]:
    
    graph = StateGraph(StateSchema)
    
    graph.add_node('pdf_loader', pdf_loader)
    graph.add_node('resume_parser', resume_parser)
    graph.add_node('store_parsed_data', store_parsed_data)
    graph.add_edge(START, 'pdf_loader')
    graph.add_edge('pdf_loader', 'resume_parser')
    graph.add_edge('resume_parser', 'store_parsed_data')
    graph.add_edge('store_parsed_data', END)
    
    complied_graph = graph.compile()
    return complied_graph