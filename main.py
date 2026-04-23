from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from utils.qdrant import connection_qdrant
from utils.embeddings import get_huggingface_embedding
from langchain_google_genai import ChatGoogleGenerativeAI
from config.env import GEMINI_API_KEY, OPENAI_API_KEY


app = FastAPI(title="Hiregenix AI (RAG)")


class CompanyChatBody(BaseModel):
    companyId: str
    query: str


def _collection_name(company_id: str) -> str:
    return f"company_kb_{company_id}"


@app.post("/rag/company-chat")
def rag_company_chat(body: CompanyChatBody):
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    if not body.companyId.strip():
        raise HTTPException(status_code=400, detail="companyId is required")

    collection = _collection_name(body.companyId.strip())
    qdrant = connection_qdrant()

    query_vec = get_huggingface_embedding(body.query.strip())

    try:
        results = qdrant.search(
            collection_name=collection,
            query_vector=query_vec,
            limit=5,
            with_payload=True,
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Knowledge base not found for company: {body.companyId}")

    contexts = []
    sources = []
    for r in results:
        payload = r.payload or {}
        txt = payload.get("text") or ""
        if txt:
            contexts.append(txt)
            sources.append(
                {
                    "score": float(r.score),
                    "chunkIndex": payload.get("chunkIndex"),
                    "pdfUrl": payload.get("pdfUrl"),
                }
            )

    context_block = "\n\n---\n\n".join(contexts) if contexts else ""

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GEMINI_API_KEY,
        temperature=0.3,
        max_output_tokens=512,
    )

    prompt = f"""
You are a helpful assistant answering questions about a company.
You MUST use only the provided context from the company's uploaded PDF.
If the answer is not in the context, say you don't know based on the document.

CONTEXT:
{context_block}

QUESTION:
{body.query.strip()}
""".strip()

    answer = llm.invoke(prompt).content
    return {"answer": answer, "sources": sources}

