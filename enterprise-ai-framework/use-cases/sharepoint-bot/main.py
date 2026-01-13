"""SharePoint Bot - Enterprise Agent for SharePoint documents.

This is a thin wiring layer that:
1. Loads configuration from agent.yaml
2. Creates the FastAPI application
3. Runs with uvicorn

Default mode: FAST_RAG
Use case: Fast Q&A over SharePoint documents with citations
"""

import os
import logging

import uvicorn

from enterprise_agent_core.api import create_app
from enterprise_agent_core.config import load_config_from_yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load configuration
config_path = os.path.join(os.path.dirname(__file__), "agent.yaml")
config = load_config_from_yaml(config_path)

# Create app
app = create_app(config)

logger.info(f"SharePoint Bot initialized: {config.name} v{config.version}")
logger.info(f"Loop mode: {config.loop_mode.value}")
logger.info(f"Knowledge index: {config.knowledge.index_name}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("ENV", "development") == "development",
    )
