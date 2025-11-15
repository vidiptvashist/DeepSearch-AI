# app/main.py
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import tempfile
from app.deps import get_current_user
import os
from app import gemini_client as gc
from dotenv import load_dotenv, find_dotenv
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

env_path = find_dotenv() or (Path(__file__).resolve().parents[1] / ".env")
load_dotenv(env_path)

app = FastAPI(title="Gemini FileSearch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  
)

# Get the correct path to static folder
# Since main.py is in backend/app/, static is at backend/static/
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# Mount static files - only if directory exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    
    # Serve index.html at root
    @app.get("/")
    async def read_root():
        return FileResponse(str(STATIC_DIR / "index.html"))
else:
    print(f"WARNING: Static directory not found at {STATIC_DIR}")
    
    @app.get("/")
    async def read_root():
        return {"message": "API is running. Static files not configured."}

# Pydantic models for request validation
class CreateStoreRequest(BaseModel):
    display_name: str


class QueryRequest(BaseModel):
    query: str


class DeleteDocumentRequest(BaseModel):
    document_resource_name: str


@app.post("/api/stores")
async def create_store(request: CreateStoreRequest, user=Depends(get_current_user)):
    user_id = user.id if hasattr(user, 'id') else user['id']
    try:
        created = gc.create_file_search_store_for_user(user_id, request.display_name)
        return {"ok": True, "store_resource": created["resource_name"], "display_name": created["display_name"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/stores/{display_name}")
async def delete_store(display_name: str, user=Depends(get_current_user)):
    user_id = user.id if hasattr(user, 'id') else user['id']
    try:
        gc.delete_store_for_user(user_id, display_name)
        return {"ok": True}
    except Exception as e:
        import traceback
        print(f"DELETE STORE ERROR: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stores")
async def list_stores(user=Depends(get_current_user)):
    user_id = user.id if hasattr(user, 'id') else user['id']
    try:
        stores = gc.list_file_search_stores_for_user(user_id)
        return {"stores": stores}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stores/{display_name}/upload")
async def upload_file(display_name: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    user_id = user.id if hasattr(user, 'id') else user['id']
    original_name = file.filename  
    try:
        # Save uploaded file to a temp path
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        try:
            result = gc.upload_file_to_store_for_user(user_id, display_name, tmp_path, original_name)
        finally:
            # ensure temp file removed even if upload fails
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        return result
    except Exception as e:
        import traceback
        print(f"UPLOAD ERROR: {str(e)}")
        traceback.print_exc()
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
async def delete_document(
    display_name: str,
    request: DeleteDocumentRequest,
    user=Depends(get_current_user),
):
    """
    Expected body: {"document_resource_name": "fileSearchStores/.../documents/..."}
    """
    user_id = user.id if hasattr(user, 'id') else user['id']
    try:
        res = gc.delete_document_from_store_for_user(user_id, display_name, request.document_resource_name)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stores/{display_name}/query")
async def query_store(
    display_name: str,
    request: QueryRequest,
    user=Depends(get_current_user),
):
    """
    Expected body: {"query": "your question here"}
    """
    user_id = user.id if hasattr(user, "id") else (user.get("id") if isinstance(user, dict) else None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthenticated")

    try:
        res = gc.query_in_store_for_user(user_id, display_name, request.query)
        return {"ok": True, "query": request.query, "result": res}
    except Exception as e:
        import traceback
        print(f"QUERY ERROR: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")
    

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)