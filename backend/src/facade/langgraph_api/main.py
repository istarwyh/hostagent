"""
LangGraph API Compatible Server

Self-hosted LangGraph API that provides endpoints compatible with @langchain/langgraph-sdk.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.app.agent_initializer import initialize_agents
from src.app.errors import AgentUnavailableError
from src.facade.langgraph_api.routers import assistants, runs, threads
from src.util.logger import setup_logger

logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Register agents when the server starts, without making provider calls."""
    initialize_agents()
    yield


app = FastAPI(
    title="LangGraph API",
    description="Self-hosted LangGraph API compatible with @langchain/langgraph-sdk",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(AgentUnavailableError)
async def agent_unavailable(request: Request, error: AgentUnavailableError):
    """Return an actionable configuration error before streaming starts."""
    return JSONResponse(status_code=503, content={"detail": str(error)})


@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    """Keep internal exception details out of HTTP responses."""
    logger.error("Unhandled API error at %s", request.url.path, exc_info=error)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(assistants.router)
app.include_router(threads.router)
app.include_router(runs.router)


@app.get("/ok")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/health")
async def health():
    """Alternative health check endpoint."""
    return {"status": "healthy", "service": "langgraph-api"}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "LangGraph API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/ok",
            "assistants": "/assistants/*",
            "threads": "/threads/*",
            "runs": "/runs/*",
        },
    }


logger.info("LangGraph API initialized")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=2024)  # nosec B104  # Development server
