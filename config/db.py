from pymongo import MongoClient
from config.env import DATABASE_URL

client = MongoClient(DATABASE_URL)

print(f"Connected to MongoDB at {DATABASE_URL}")
db = client["hiregenix"]

task_collection = db["tasks"]
resume_collection = db["resumes"]