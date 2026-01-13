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
from agentic_rag_core import (
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
app = FastAPI(
    title="Nigerian Tax Reform Q&A Assistant",
    description="Agentic RAG system for tax reform queries",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            documents_folder="ai_engine\documents"  # Adjust path
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