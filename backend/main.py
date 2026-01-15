from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os

# Prefer the .env file located inside the backend package directory so
# environment values (like OPENAI_API_KEY) are loaded when running
# `uvicorn backend.main:app` from the repo root.
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    # Fallback to default behavior (search current working dir / parents)
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
    # Log header presence for debugging auth issues
    logger = logging.getLogger("backend.main")
    logger.debug(f"Authorization header received: {bool(auth_header)}")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.debug("Authorization header missing or malformed")
        return None
    token = auth_header.split(" ", 1)[1]
    payload = auth.decode_token(token)
    if not payload or "sub" not in payload:
        logger.debug("Token decode failed or missing 'sub' claim")
        return None
    try:
        user_id = int(payload["sub"])
    except Exception:
        logger.debug("Invalid user id in token payload")
        return None
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        logger.debug(f"No user found for id {user_id}")
    return user

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
            # Extract document sources from context
            sources = []
            if retrieved:
                if isinstance(retrieved, list):
                    sources = [{"document": r.get("source", "Unknown"), "excerpt": r.get("content", "")[:200]} for r in retrieved]
                elif isinstance(retrieved, dict):
                    sources = [{"document": retrieved.get("source", "Unknown"), "excerpt": retrieved.get("content", "")[:200]}]
        else:
            reply_text = "RAG system not initialized. Try again later."
            retrieved = None
            sources = []
    except Exception as e:
        reply_text = f"Error generating response: {str(e)}"
        retrieved = None
        sources = []

    assistant_msg = models.Message(chat_id=chat.id, role="assistant", content=reply_text)
    db.add(assistant_msg)
    db.commit()

    # Return full messages for the chat
    msgs = db.query(models.Message).filter(models.Message.chat_id == chat.id).order_by(models.Message.created_at).all()
    messages_out = [
        {"id": m.id, "chat_id": m.chat_id, "role": m.role, "content": m.content, "created_at": m.created_at}
        for m in msgs
    ]

    return {"chat_id": chat.id, "reply": reply_text, "retrieved_context": retrieved, "sources": sources, "messages": messages_out}










"""
FastAPI Backend for Agentic RAG Tax Q&A System
Nigerian Tax Reform Q&A Assistant
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from enum import Enum
import asyncio
import logging
import uuid
from datetime import datetime
import json
from io import BytesIO
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

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
    # If the OpenAI API key is not provided, skip RAG initialization so the
    # backend can run for other functionality (auth, chats, health) without
    # failing at startup.
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not set — skipping RAG initialization. RAG features disabled.")
        rag_generator = None
        vectorstore_manager = None
        return

    try:
        logger.info("Starting up agentic RAG system...")

        # Build the RAG system
        doc_processor, vectorstore_manager, rag_generator = await build_agentic_rag_system(
            documents_folder="ai_engine/documents"
        )

        logger.info("RAG system initialized successfully")

    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        logger.exception(e)
        # Do not re-raise so the API stays available even if RAG init fails
        rag_generator = None
        vectorstore_manager = None


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


# TAX CALCULATOR ENDPOINT
@app.post("/calculator")
def calculate_tax(calc_req: schemas.TaxCalculatorRequest):
    """
    Calculate tax scenarios for Nigerian taxes.
    Supports VAT, income tax, and corporate income tax calculations.
    """
    try:
        tax_type = calc_req.tax_type.lower()
        
        # VAT Calculation (7.5% standard rate in Nigeria)
        if tax_type == "vat" and calc_req.purchase_amount:
            vat_rate = 0.075
            tax_amount = calc_req.purchase_amount * vat_rate
            return schemas.TaxCalculatorResponse(
                tax_type="VAT",
                gross_amount=calc_req.purchase_amount,
                tax_amount=round(tax_amount, 2),
                net_amount=round(calc_req.purchase_amount + tax_amount, 2),
                tax_rate=vat_rate,
                description=f"Nigerian VAT at {vat_rate*100}% on ₦{calc_req.purchase_amount:,.2f}"
            )
        
        # Income Tax Calculation (Progressive rates in Nigeria)
        elif tax_type == "income_tax" and calc_req.gross_income:
            income = calc_req.gross_income
            # Simplified progressive tax brackets for Nigeria
            if income <= 300000:
                tax_amount = 0
            elif income <= 600000:
                tax_amount = (income - 300000) * 0.07
            elif income <= 1800000:
                tax_amount = 21000 + (income - 600000) * 0.11
            else:
                tax_amount = 153200 + (income - 1800000) * 0.15
            
            tax_rate = tax_amount / income if income > 0 else 0
            return schemas.TaxCalculatorResponse(
                tax_type="Personal Income Tax",
                gross_amount=income,
                tax_amount=round(tax_amount, 2),
                net_amount=round(income - tax_amount, 2),
                tax_rate=round(tax_rate, 4),
                description=f"Nigerian personal income tax on ₦{income:,.2f}"
            )
        
        # Corporate Income Tax (30% standard rate)
        elif tax_type == "cit" and calc_req.gross_income:
            cit_rate = 0.30
            tax_amount = calc_req.gross_income * cit_rate
            return schemas.TaxCalculatorResponse(
                tax_type="Corporate Income Tax",
                gross_amount=calc_req.gross_income,
                tax_amount=round(tax_amount, 2),
                net_amount=round(calc_req.gross_income - tax_amount, 2),
                tax_rate=cit_rate,
                description=f"Nigerian CIT at {cit_rate*100}% on ₦{calc_req.gross_income:,.2f}"
            )
        
        else:
            raise HTTPException(status_code=400, detail="Invalid tax type or missing amount")
            
    except Exception as e:
        logger.error(f"Calculator error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)}")


# CHAT EXPORT ENDPOINT
@app.post("/chats/{chat_id}/export")
def export_chat(chat_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Export a chat conversation as PDF or JSON.
    """
    user = get_user_from_auth_header(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id, models.Chat.user_id == user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    msgs = db.query(models.Message).filter(models.Message.chat_id == chat.id).order_by(models.Message.created_at).all()
    
    try:
        # Export as PDF if reportlab is available
        if REPORTLAB_AVAILABLE:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
            story = []
            styles = getSampleStyleSheet()
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                textColor='#0b8a5f',
                spaceAfter=12,
            )
            story.append(Paragraph(f"Nigeria Tax Reform Q&A - Chat Export", title_style))
            story.append(Paragraph(f"Date: {chat.created_at.strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            story.append(Spacer(1, 0.3*inch))
            
            # Messages
            for msg in msgs:
                role_label = "You" if msg.role == "user" else "FIRS Assistant"
                msg_style = ParagraphStyle(
                    f'msg_{msg.role}',
                    parent=styles['Normal'],
                    textColor='#0b8a5f' if msg.role == "assistant" else '#000000',
                    fontSize=10,
                    spaceAfter=6,
                    leftIndent=18,
                )
                timestamp = msg.created_at.strftime('%H:%M') if msg.created_at else ""
                story.append(Paragraph(f"<b>{role_label}</b> ({timestamp})", styles['Normal']))
                story.append(Paragraph(msg.content, msg_style))
                story.append(Spacer(1, 0.1*inch))
            
            doc.build(story)
            buffer.seek(0)
            
            return StreamingResponse(
                iter([buffer.getvalue()]),
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=chat_{chat_id}.pdf"}
            )
        else:
            # Fallback to JSON export
            export_data = {
                "chat_id": chat.id,
                "created_at": chat.created_at.isoformat(),
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "timestamp": m.created_at.isoformat() if m.created_at else None
                    }
                    for m in msgs
                ]
            }
            return JSONResponse(export_data)
            
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


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