"""FastAPI application factory for Enterprise Agent.

Creates and configures the FastAPI application with all
dependencies wired up. Production-safe defaults are applied.

Security:
- CORS origins must be explicitly configured (no wildcard by default)
- mock_mode reads from config/environment, defaults to False
"""

import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from ..config import AgentConfig, load_config_from_yaml
from ..engine.workflow import AgentWorkflowEngine
from ..engine.modes import LoopMode
from ..engine.routers.classic import ClassicRouter
from ..engine.routers.maf_preview import MAFRouter
from ..planning.basic_planner import BasicPlanner
from ..retrieval import RetrieverFactory
from ..critic.basic_critic import BasicCritic
from ..synthesis.basic_synthesizer import BasicSynthesizer
from ..tools.executor import BasicToolExecutor

logger = logging.getLogger(__name__)


def create_app(
    config: Optional[AgentConfig] = None,
    config_path: Optional[str] = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Pre-loaded AgentConfig
        config_path: Path to agent.yaml (used if config not provided)

    Returns:
        Configured FastAPI application
    """
    # Load config
    if config is None and config_path:
        config = load_config_from_yaml(config_path)
    elif config is None:
        config = AgentConfig()

    # Create FastAPI app
    app = FastAPI(
        title=f"Enterprise Agent API - {config.name}",
        version=config.version,
        description="Enterprise AI Agent with cognitive loop architecture",
    )

    # Configure CORS with security-aware defaults
    _configure_cors(app, config)

    # Include routes
    app.include_router(router)

    # Store config in app state
    app.state.config = config

    # Create and wire up engine with factory
    retriever_factory = RetrieverFactory(config)
    engine = create_engine(config, retriever_factory)
    
    app.state.engine = engine
    app.state.retriever_factory = retriever_factory

    logger.info(
        f"Created Enterprise Agent app: {config.name} v{config.version}, "
        f"loop_mode={config.loop_mode.value}, "
        f"mock_mode={config.knowledge.mock_mode}"
    )

    return app


def _configure_cors(app: FastAPI, config: AgentConfig) -> None:
    """Configure CORS middleware with security-aware defaults.
    
    Args:
        app: FastAPI application
        config: Agent configuration with CORS settings
    """
    cors_config = config.cors
    
    # Check if any origins are configured
    if not cors_config.allowed_origins:
        logger.warning(
            "No CORS origins configured. API will not accept cross-origin requests. "
            "Set cors.allowed_origins in agent.yaml for browser-based clients."
        )
        return

    # Warn about wildcard in production
    if cors_config.is_development_mode():
        import os
        if os.environ.get("ENV", "production") == "production":
            logger.warning(
                "CORS wildcard '*' detected in production environment! "
                "This is a security risk. Configure explicit allowed_origins."
            )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config.allowed_origins,
        allow_credentials=cors_config.allow_credentials,
        allow_methods=cors_config.allowed_methods,
        allow_headers=cors_config.allowed_headers,
    )

    logger.info(f"CORS configured with origins: {cors_config.allowed_origins}")


def create_engine(
    config: AgentConfig,
    retriever_factory: Optional[RetrieverFactory] = None,
) -> AgentWorkflowEngine:
    """Create the workflow engine with all components.

    Args:
        config: Agent configuration
        retriever_factory: Optional pre-configured RetrieverFactory

    Returns:
        Configured AgentWorkflowEngine
    """
    # Create router based on config
    if config.enable_maf_router:
        router_instance = MAFRouter(
            config=config,
            default_loop_mode=config.loop_mode,
        )
        logger.info("Using MAFRouter (preview)")
    else:
        router_instance = ClassicRouter(
            config=config,
            default_loop_mode=config.loop_mode,
        )
        logger.info("Using ClassicRouter (stable)")

    # Create planner
    planner = BasicPlanner(
        default_top_k=config.knowledge.default_top_k,
    )

    # Create retriever factory if not provided
    if retriever_factory is None:
        retriever_factory = RetrieverFactory(config)

    # Get default retriever - engine will use factory for per-request selection
    retriever = retriever_factory.get_default_retriever()

    # Create critic
    critic = BasicCritic()

    # Create synthesizer
    synthesizer = BasicSynthesizer(
        model_deployment=config.model_deployment,
    )

    # Create tool executor with config-driven approval settings
    logic_apps = {la.name: la for la in config.logic_apps}
    tool_executor = BasicToolExecutor(
        logic_apps=logic_apps,
        default_timeout_ms=30000,
    )

    # Create engine
    engine = AgentWorkflowEngine(
        router=router_instance,
        planner=planner,
        retriever=retriever,
        critic=critic,
        synthesizer=synthesizer,
        tool_executor=tool_executor,
        budget=config.budget,
        agent_name=config.name,
        default_loop_mode=config.loop_mode,
    )

    logger.info(
        f"Created AgentWorkflowEngine with budget: "
        f"max_iterations={config.budget.max_iterations}, "
        f"max_latency_ms={config.budget.max_latency_ms}, "
        f"retriever_mock_mode={config.knowledge.mock_mode}"
    )

    return engine

