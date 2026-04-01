from pymongo import MongoClient
from config.env import DATABASE_URL

client = MongoClient(DATABASE_URL)

print(f"Connected to MongoDB at {DATABASE_URL}")
db = client["hiregenix"]

user_collection = db["users"]
task_collection = db["tasks"]
resume_collection = db["resumes"]
candidate_collection = db["candidates"]
job_collection = db["jobs"]
recommended_jobs_collection = db["recommendedjobs"]
company_collection = db["companies"]
question_result_collection = db["questionresults"]
interview_collection = db["interviews"]
report_collection = db["reports"]