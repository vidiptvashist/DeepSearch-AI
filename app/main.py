# app/main.py
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import shutil
import tempfile
import os
import re
import json
from app.deps import get_current_user, supabase
from app import gemini_client as gc
from dotenv import load_dotenv, find_dotenv
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

env_path = find_dotenv() or (Path(__file__).resolve().parents[1] / ".env")
load_dotenv(env_path)

app = FastAPI(title="DeepSearch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    @app.get("/")
    async def read_root():
        return FileResponse(str(STATIC_DIR / "index.html"))
else:
    @app.get("/")
    async def read_root():
        return {"message": "API running. Static files not found."}

# --- Models ---
class CreateStoreRequest(BaseModel):
    display_name: str

class QueryRequest(BaseModel):
    query: str
    system_instruction: Optional[str] = None

class EnhancePromptRequest(BaseModel):
    prompt: str

class DeleteDocumentRequest(BaseModel):
    document_resource_name: str

# --- Helpers ---
def db_get_history(user_id: str, store_name: str, limit: int = 50):
    """Fetch chat history. Returns Oldest -> Newest for UI."""
    try:
        # 1. Get the last N messages (descending)
        response = supabase.table("chat_messages")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("store_name", store_name)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        data = response.data if response.data else []
        # 2. Reverse them so they are Chronological (Oldest first)
        return data[::-1] 
    except Exception as e:
        print(f"DB GET ERROR: {e}")
        return []

def db_save_message(user_id: str, store_name: str, role: str, content: str, suggestions: list = None, citations: list = None):
    try:
        data = {
            "user_id": user_id,
            "store_name": store_name,
            "role": role,
            "content": content,
            "suggestions": suggestions,
            "citations": citations 
        }
        supabase.table("chat_messages").insert(data).execute()
    except Exception as e:
        print(f"DB SAVE ERROR (Non-fatal): {e}")
        # We catch this so the API request doesn't fail even if DB save fails

# --- Endpoints ---

@app.get("/api/stores")
async def list_stores(user=Depends(get_current_user)):
    user_id = user.id if hasattr(user, 'id') else user['id']
    try:
        stores = gc.list_file_search_stores_for_user(user_id)
        return {"stores": stores}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stores")
async def create_store(request: CreateStoreRequest, user=Depends(get_current_user)):
    user_id = user.id if hasattr(user, 'id') else user['id']
    try:
        created = gc.create_file_search_store_for_user(user_id, request.display_name)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/stores/{display_name}")
async def delete_store(display_name: str, user=Depends(get_current_user)):
    user_id = user.id if hasattr(user, 'id') else user['id']
    try:
        gc.delete_store_for_user(user_id, display_name)
        try:
            supabase.table("chat_messages").delete().eq("store_name", display_name).eq("user_id", user_id).execute()
        except:
            pass # Ignore DB delete errors if table doesn't exist
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stores/{display_name}/upload")
async def upload_file(display_name: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    user_id = user.id if hasattr(user, 'id') else user['id']
    original_name = file.filename  
    try:
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        try:
            result = gc.upload_file_to_store_for_user(user_id, display_name, tmp_path, original_name)
        finally:
            try: os.remove(tmp_path)
            except: pass
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stores/{display_name}/documents")
async def list_documents(display_name: str, user=Depends(get_current_user)):
    user_id = user.id if hasattr(user, 'id') else user['id']
    try:
        docs = gc.list_documents_in_store_for_user(user_id, display_name)
        return {"documents": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/stores/{display_name}/documents")
async def delete_document(display_name: str, request: DeleteDocumentRequest, user=Depends(get_current_user)):
    user_id = user.id if hasattr(user, 'id') else user['id']
    try:
        res = gc.delete_document_from_store_for_user(user_id, display_name, request.document_resource_name)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stores/{display_name}/chat")
async def get_chat_history(display_name: str, user=Depends(get_current_user)):
    user_id = user.id if hasattr(user, 'id') else user['id']
    history = db_get_history(user_id, display_name, limit=50)
    return {"history": history}

@app.post("/api/stores/{display_name}/query")
async def query_store(display_name: str, request: QueryRequest, user=Depends(get_current_user)):
    user_id = user.id if hasattr(user, "id") else (user.get("id") if isinstance(user, dict) else None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthenticated")

    try:
        # 1. Get Context (Last 6)
        db_history = db_get_history(user_id, display_name, limit=6)
        gemini_history = [{"role": msg['role'], "content": msg['content']} for msg in db_history]

        # 2. Save User Query
        db_save_message(user_id, display_name, "user", request.query)

        # 3. Call Gemini
        # raw_res is now a dict: {"text": ..., "citations": ..., "suggestions": ...}
        raw_res = gc.query_in_store_for_user(user_id, display_name, request.query, gemini_history, request.system_instruction)

        # 4. Parse Response (Suggestions & Citations)
        # gemini_client already did the parsing
        ai_content = raw_res.get("text", "")
        suggestions = raw_res.get("suggestions", [])
        citations = raw_res.get("citations", [])

        # 5. Save Model Response
        db_save_message(user_id, display_name, "model", ai_content, suggestions, citations)

        return {"ok": True, "result": ai_content, "suggestions": suggestions, "citations": citations}
    except Exception as e:
        print(f"QUERY ERROR: {str(e)}")
        # Return error as result so UI doesn't crash on 500
        return {"ok": False, "result": f"I encountered an error processing your request: {str(e)}", "suggestions": [], "citations": []}

@app.post("/api/enhance_prompt")
async def enhance_prompt(request: EnhancePromptRequest, user=Depends(get_current_user)):
    try:
        enhanced = gc.enhance_system_prompt(request.prompt)
        return {"enhanced_prompt": enhanced}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stores/{display_name}/graph")
async def get_graph(display_name: str, user=Depends(get_current_user)):
    user_id = user.id if hasattr(user, 'id') else user['id']
    try:
        graph_data = gc.generate_knowledge_graph(user_id, display_name)
        return graph_data
    except Exception as e:
        print(f"Graph Error: {e}")
        return {"nodes": [], "links": []}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)