import uvicorn
from loguru import logger
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from src.pipeline_react import MultiAgentsReAct
from src.config.schemas import ChatRequest, ChatResponse
from src.utils.metrics import get_metrics_collector, RequestTimer, record_request_metric

async def startup_hook(app: FastAPI):
    """Initialize multi-agent system on startup."""
    try:
        app.state.multi_agents = MultiAgentsReAct()
        logger.info("Multi Agents system started successfully")
    except Exception as e:
        logger.error(f"Failed to start Multi Agents: {e}", exc_info=True)
        raise

async def shutdown_hook(app: FastAPI):
    """Cleanup on shutdown."""
    metrics = get_metrics_collector()
    metrics.log_metrics()
    
    app.state.multi_agents = None
    logger.info("Multi Agents system shut down")
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    await startup_hook(app)
    yield
    await shutdown_hook(app)
    
app = FastAPI(
    title="Multi-Agent Sales Assistant API",
    description="AI-powered multi-agent system for sales consultation and order processing",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

@app.get("/", summary="Root endpoint")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Multi-Agent Sales Assistant API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "chat": "/chat",
            "health": "/health",
            "metrics": "/metrics",
            "docs": "/docs"
        }
    }

@app.get("/health", summary="Health check")
async def health_check():
    """
    Health check endpoint to verify system status.
    """
    try:
        is_healthy = hasattr(app.state, 'multi_agents') and app.state.multi_agents is not None
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "multi_agents_initialized": is_healthy
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.get("/metrics", summary="Get system metrics")
async def get_metrics():
    """
    Get current system metrics and statistics.
    
    Returns:
        Dictionary containing system metrics
    """
    try:
        metrics = get_metrics_collector()
        return metrics.get_metrics()
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.post("/chat", response_model=ChatResponse, summary="Chat with Multi Agents")
async def chat(request: ChatRequest):
    """
    Process customer query through the multi-agent system.
    
    Args:
        request (ChatRequest): Chat request with query and optional context
        
    Returns:
        ChatResponse: Structured response from the multi-agent system
        
    Raises:
        HTTPException: If the system is not initialized or processing fails
    """
    with RequestTimer("chat_request") as timer:
        try:
            # Validate system is ready
            if not hasattr(app.state, 'multi_agents') or app.state.multi_agents is None:
                raise HTTPException(
                    status_code=503,
                    detail="Multi-agent system is not initialized"
                )
            
            # Log request
            logger.info(f"Processing chat request: {request.query[:100]}...")
            
            # Process query
            response = await app.state.multi_agents.run(
                query=request.query,
                initial_context_data=request.initial_context_data,
                user_id=request.user_id or "default_user",
                session_id=request.session_id
            )
            
            # Build response
            chat_response = ChatResponse(
                customer_response=response.get('customer_response', ''),
                status=response.get('status', 'unknown'),
                session_id=response.get('session_id'),
                token_usage=response.get('token_usage'),
                error=response.get('error')
            )
            
            # Record metrics
            success = chat_response.status == 'success'
            tokens = chat_response.token_usage.get('total_tokens', 0) if chat_response.token_usage else 0
            
            record_request_metric(
                success=success,
                response_time=timer.get_elapsed(),
                tokens_used=tokens,
                error_type=chat_response.error if not success else None
            )
            
            # Log result
            if success:
                logger.info(f"✅ Successfully processed request for session: {chat_response.session_id}")
            else:
                logger.warning(f"⚠️ Request completed with errors: {chat_response.error}")
            
            return chat_response
            
        except HTTPException:
            record_request_metric(
                success=False,
                response_time=timer.get_elapsed(),
                error_type="HTTPException"
            )
            raise
        except Exception as e:
            logger.error(f"❌ Error processing chat request: {e}", exc_info=True)
            record_request_metric(
                success=False,
                response_time=timer.get_elapsed(),
                error_type=type(e).__name__
            )
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error: {str(e)}"
            )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": str(exc),
            "detail": "An unexpected error occurred"
        }
    )

if __name__ == "__main__":
    logger.info("🚀 Starting Multi-Agent Sales Assistant API server...")
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=2206,
        log_level="info"
    )