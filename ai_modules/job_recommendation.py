from config.db import recommended_jobs_collection, candidate_collection, job_collection, company_collection
from bson import ObjectId
from utils.qdrant import connection_qdrant
from models.recommended_jobs import RecommendedJobs
from datetime import datetime

def run_recommendation_pipeline(candidate_id):
    try:
        # recommended_jobs_collection.find_one({"_id": ObjectId(candidate_id)})
        candidate = candidate_collection.find_one({"_id": ObjectId(candidate_id)})
        
        if not candidate:
            print("❌ Candidate not found in DB")
            return
        
        # print(f" 🔍 Fetched Candidate {candidate_id} from DB: {candidate}")
        
        qdrant_id = candidate.get("qdrantId")
        
        # print(f"Qdrant ID: {qdrant_id}")
        
        client = connection_qdrant()
        
        candidate_point = client.retrieve(collection_name="candidate", ids=[qdrant_id], with_vectors=True, with_payload=True)[0]
        candidate_vector = candidate_point.vector
        # print(f"Candidate Vector: {candidate_vector}")
        
        result = client.query_points(collection_name="job", limit=2, query=candidate_vector)
        
        recommended_jobs=[]
        
        for r in result.points:
            print(r.payload.get("job_id"))
            job = job_collection.find_one({"_id": ObjectId(r.payload.get("job_id"))})
            
            if not job:
                print("❌ Job not found in DB")
                continue
            
            if job.get("isDeleted") == "true":
                print("❌ Job is deleted")
                continue
            
            company = company_collection.find_one({"_id": ObjectId(job.get("companyId"))})
            
            if not company:
                print("❌ Company not found in DB")
                continue
            
            
            job_object = {
                "jobId": str(job.get("_id")),
                "title": job.get("title"),
                "companyName": company.get("companyName"),
                "companyLogo": company.get("logoUrl"),
                "role": job.get("role"),
                "workMode": job.get("workMode"),
                "requiredSkills": job.get("requiredSkills"),
                "salaryRange": job.get("salaryRange"),
                "description": job.get("description"),
                "requirements": job.get("requirements"),
                "location": job.get("location"),
                "aiSummary": job.get("aiSummary"),
                "createdAt": job.get("createdAt"),
                "updatedAt": job.get("updatedAt")
            }
            recommended_jobs.append(job_object)
        
        print(f"Recommended Jobs:{recommended_jobs}")
        
        doc = RecommendedJobs(
            candidateId=ObjectId(candidate_id),
            recommendedJobs=recommended_jobs,
            createdAt=datetime.utcnow(),
            updatedAt=datetime.utcnow()
        )
        
        doc_dict = doc.model_dump(by_alias=True)
        doc_dict.pop("_id", None)
        doc_dict.pop("createdAt", None)  # avoid conflict

        recommended_jobs_collection.update_one(
            {"candidateId": ObjectId(candidate_id)},
            {
                "$set": {**doc_dict, "updatedAt": datetime.utcnow()},
                "$setOnInsert": {"createdAt": datetime.utcnow()},
            },
            upsert=True
        )


        
        print("✅ Recommendation pipeline completed successfully")
        return True
    except Exception as e:
        print(f"❌ Error in recommendation pipeline: {e}")
        return False