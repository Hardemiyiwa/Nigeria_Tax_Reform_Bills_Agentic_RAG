from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os

load_dotenv()

from . import models, schemas, auth
from .database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGINS", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_current_user(token: str = Depends(lambda request: None)):
    # We'll implement a token extractor inside endpoints for clarity
    return None

@app.post("/auth/signup")
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_obj = models.User(email=user.email, password_hash=auth.get_password_hash(user.password))
    db.add(user_obj)
    db.commit()
    db.refresh(user_obj)
    token = auth.create_access_token({"sub": str(user_obj.id)})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/auth/login")
def login(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not auth.verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    token = auth.create_access_token({"sub": str(db_user.id)})
    return {"access_token": token, "token_type": "bearer"}

def get_user_from_auth_header(request: Request, db: Session):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    payload = auth.decode_token(token)
    if not payload or "sub" not in payload:
        return None
    user_id = int(payload["sub"])
    return db.query(models.User).filter(models.User.id == user_id).first()

@app.post("/chat")
def chat_endpoint(req: schemas.ChatRequest, request: Request, db: Session = Depends(get_db)):
    user = get_user_from_auth_header(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # If chat_id not provided, create a new chat
    if not req.chat_id:
        chat = models.Chat(user_id=user.id)
        db.add(chat)
        db.commit()
        db.refresh(chat)
    else:
        chat = db.query(models.Chat).filter(models.Chat.id == req.chat_id, models.Chat.user_id == user.id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

    # Save user message
    message = models.Message(chat_id=chat.id, role="user", content=req.message)
    db.add(message)
    db.commit()

    # Integrate with Agentic RAG generator if available
    try:
        if 'rag_generator' in globals() and rag_generator:
            result = rag_generator.query(user_input=req.message, thread_id=str(chat.id))
            reply_text = result.get('answer') or "I couldn't find an answer in the knowledge base."
            retrieved = result.get('context') if isinstance(result, dict) else None
        else:
            reply_text = "RAG system not initialized. Try again later."
            retrieved = None
    except Exception as e:
        reply_text = f"Error generating response: {str(e)}"
        retrieved = None

    assistant_msg = models.Message(chat_id=chat.id, role="assistant", content=reply_text)
    db.add(assistant_msg)
    db.commit()

    # Return full messages for the chat
    msgs = db.query(models.Message).filter(models.Message.chat_id == chat.id).order_by(models.Message.created_at).all()
    messages_out = [
        {"id": m.id, "chat_id": m.chat_id, "role": m.role, "content": m.content, "created_at": m.created_at}
        for m in msgs
    ]

    return {"chat_id": chat.id, "reply": reply_text, "retrieved_context": retrieved, "messages": messages_out}










"""
FastAPI Backend for Agentic RAG Tax Q&A System
Nigerian Tax Reform Q&A Assistant
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from enum import Enum
import asyncio
import logging
import uuid
from datetime import datetime

# Import your agentic RAG core
from ai_engine.agentic_rag_core import (
    build_agentic_rag_system,
    AgenticRAGGenerator,
    VectorStoreManager,
)

# LOGGING SETUP
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# PYDANTIC MODELS (Request/Response Schemas)

class QueryRequest(BaseModel):
    """
    Request model for Q&A queries
    """
    question: str = Field(..., min_length=1, max_length=2000, description="Tax-related question")
    thread_id: Optional[str] = Field(None, description="Conversation thread ID for memory")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is the current VAT rate in Nigeria?",
                "thread_id": "user_123"
            }
        }


class QueryResponse(BaseModel):
    """
    Response model for Q&A queries
    """
    query_id: str
    question: str
    answer: str
    timestamp: datetime
    thread_id: str
    confidence: Optional[str] = None
    retrieved_context: Optional[List[Dict]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "query_id": "q_uuid_here",
                "question": "What is the current VAT rate?",
                "answer": "The VAT rate in Nigeria is 7.5%...",
                "timestamp": "2026-01-07T18:30:00",
                "thread_id": "user_123",
                "confidence": "high"
            }
        }



class HealthCheckResponse(BaseModel):
    """
    Health check response
    """
    status: str
    message: str
    timestamp: datetime


# FASTAPI APP INITIALIZATION
# `app` already created above; set metadata instead of re-declaring
app.title = "Nigerian Tax Reform Q&A Assistant"
app.description = "Agentic RAG system for tax reform queries"
app.version = "1.0.0"

# GLOBAL STATE
vectorstore_manager: Optional[VectorStoreManager] = None
rag_generator: Optional[AgenticRAGGenerator] = None

# Tracking metrics
query_counter = 0
active_threads: Dict[str, datetime] = {}


# STARTUP & SHUTDOWN EVENTS
@app.on_event("startup")
async def startup_event():
    """
    Initialize RAG system on startup
    """
    global rag_generator, vectorstore_manager
    
    try:
        logger.info("Starting up agentic RAG system...")
        
        # Build the RAG system
        doc_processor, vectorstore_manager, rag_generator = await build_agentic_rag_system(
            documents_folder="ai_engine/documents"
        )
        
        logger.info("RAG system initialized successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup on shutdown
    """
    logger.info("Shutting down system...")
    # Add cleanup logic if needed


# HEALTH & STATUS ENDPOINTS
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check endpoint
    """
    return HealthCheckResponse(
        status="healthy" if rag_generator else "initializing",
        message="System is operational",
        timestamp=datetime.utcnow()
    )


# MAIN Q&A ENDPOINT
@app.post("/query", response_model=QueryResponse)
async def submit_query(request: QueryRequest):
    """
    Submit a tax-related question and get an answer from the agentic RAG system.
    
    - Validates question
    - Routes to RAG agent
    - Maintains conversation thread
    - Returns answer with optional context
    """
    global query_counter, active_threads
    
    if not rag_generator:
        raise HTTPException(
            status_code=503,
            detail="RAG system not initialized. Please try again later."
        )
    
    try:
        # Generate IDs
        query_id = str(uuid.uuid4())[:8]
        thread_id = request.thread_id or f"thread_{uuid.uuid4()}"
        
        # Update thread tracking
        active_threads[thread_id] = datetime.utcnow()
        
        logger.info(f"Processing query: {query_id} | Thread: {thread_id}")
        logger.info(f"Question: {request.question[:100]}...")
        
        # Call agentic RAG (synchronous call, wrap if needed)
        result = rag_generator.query(
            user_input=request.question,
            thread_id=thread_id
        )
        
        query_counter += 1
        
        # Determine confidence based on answer presence
        confidence = "high" if result.get("answer") else "low"
        
        return QueryResponse(
            query_id=query_id,
            question=request.question,
            answer=result.get("answer", "Unable to provide an answer"),
            retrieved_context=result.get("context"),
            timestamp=datetime.utcnow(),
            thread_id=thread_id,
            confidence=confidence
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )



# THREAD MANAGEMENT ENDPOINTS
@app.get("/threads/{thread_id}")
async def get_thread_info(thread_id: str):
    """
    Get conversation thread metadata
    """
    if thread_id not in active_threads:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    return {
        "thread_id": thread_id,
        "created_at": active_threads[thread_id],
        "status": "active"
    }


@app.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    """
    Clear conversation memory for a thread
    """
    if thread_id in active_threads:
        del active_threads[thread_id]
        logger.info(f"Thread {thread_id} cleared")
        return {"status": "success", "message": f"Thread {thread_id} deleted"}
    
    raise HTTPException(status_code=404, detail="Thread not found")


# New chat history endpoints
@app.get("/chats")
def list_chats(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_auth_header(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    chats = db.query(models.Chat).filter(models.Chat.user_id == user.id).order_by(models.Chat.created_at.desc()).all()
    result = []
    for c in chats:
        last_msg = None
        if c.messages:
            last_msg = c.messages[-1].content
        result.append({"id": c.id, "user_id": c.user_id, "created_at": c.created_at, "last_message": last_msg})

    return {"chats": result}


@app.get("/chats/{chat_id}")
def get_chat_messages(chat_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_from_auth_header(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    chat = db.query(models.Chat).filter(models.Chat.id == chat_id, models.Chat.user_id == user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    msgs = db.query(models.Message).filter(models.Message.chat_id == chat.id).order_by(models.Message.created_at).all()
    messages_out = [
        {"id": m.id, "chat_id": m.chat_id, "role": m.role, "content": m.content, "created_at": m.created_at}
        for m in msgs
    ]

    return {"chat": {"id": chat.id, "user_id": chat.user_id, "created_at": chat.created_at, "messages": messages_out}}


# ERROR HANDLERS
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """
    Custom HTTP exception handler
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "detail": exc.detail,
            "timestamp": datetime.utcnow().isoformat()
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """
    Catch-all exception handler
    """
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "status_code": 500,
            "detail": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        },
    )


# ROOT ENDPOINT
@app.get("/")
async def root():
    """
    Root endpoint with API documentation
    """
    return {
        "name": "Nigerian Tax Reform Q&A Assistant",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "query": "POST /query",
            "docs": "/docs"
        }
    }


# RUN APPLICATION
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False  # Set to True for development
    )