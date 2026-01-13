"""Tests for config parsing and normalization.

Tests the agent.yaml loading, environment variable expansion,
and config normalization for nested structures.
"""

import os
import tempfile
import pytest
from unittest.mock import patch

from enterprise_agent_core.config import (
    AgentConfig,
    CORSConfig,
    KnowledgeConfig,
    WorkflowConfig,
    AISearchFieldConfig,
    load_config_from_yaml,
)
from enterprise_agent_core.engine.modes import LoopMode


class TestConfigDefaults:
    """Test configuration default values."""

    def test_cors_default_no_origins(self):
        """CORS should default to no allowed origins (production-safe)."""
        config = CORSConfig()
        assert config.allowed_origins == []
        assert config.is_development_mode() is False

    def test_cors_detects_development_mode(self):
        """Wildcard origin should be flagged as development mode."""
        config = CORSConfig(allowed_origins=["*"])
        assert config.is_development_mode() is True

    def test_knowledge_mock_mode_default_false(self):
        """mock_mode should default to False for production safety."""
        config = KnowledgeConfig()
        assert config.mock_mode is False

    def test_knowledge_mock_mode_from_env(self):
        """mock_mode should read from MOCK_MODE environment variable."""
        with patch.dict(os.environ, {"MOCK_MODE": "true"}):
            config = KnowledgeConfig()
            assert config.mock_mode is True

        with patch.dict(os.environ, {"MOCK_MODE": "false"}):
            config = KnowledgeConfig()
            assert config.mock_mode is False

    def test_field_config_defaults(self):
        """AISearchFieldConfig should have sensible defaults."""
        config = AISearchFieldConfig()
        assert config.vector_field == "contentVector"
        assert config.content_field == "content"
        assert config.title_field == "title"
        assert config.url_field == "url"
        assert config.id_field == "id"


class TestYAMLLoading:
    """Test loading configuration from YAML files."""

    def test_load_simple_config(self):
        """Load a minimal agent.yaml config."""
        yaml_content = """
project:
  name: test-bot
  version: 1.0.0

workflow:
  default_mode: plan_rag
  allowed_modes:
    - fast_rag
    - plan_rag
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            config = load_config_from_yaml(f.name)
            
            assert config.name == "test-bot"
            assert config.version == "1.0.0"
            assert config.workflow.default_mode == LoopMode.PLAN_RAG
            assert len(config.workflow.allowed_modes) == 2
        
        os.unlink(f.name)

    def test_mode_case_normalization(self):
        """Uppercase modes in YAML should be normalized to lowercase."""
        yaml_content = """
project:
  name: case-test
workflow:
  default_mode: PLAN_RAG
  allowed_modes:
    - FAST_RAG
    - FULL_ACTOR_CRITIC
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            config = load_config_from_yaml(f.name)
            
            # Should be lowercased
            assert config.workflow.default_mode == LoopMode.PLAN_RAG
            assert LoopMode.FAST_RAG in config.workflow.allowed_modes
            assert LoopMode.FULL_ACTOR_CRITIC in config.workflow.allowed_modes
        
        os.unlink(f.name)

    def test_env_variable_expansion(self):
        """Environment variables should be expanded in YAML values."""
        yaml_content = """
project:
  name: env-test
  project_endpoint: ${TEST_PROJECT_ENDPOINT}

retrieval:
  ai_search:
    endpoint: ${TEST_SEARCH_ENDPOINT}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            with patch.dict(os.environ, {
                "TEST_PROJECT_ENDPOINT": "https://foundry.azure.com",
                "TEST_SEARCH_ENDPOINT": "https://search.azure.com",
            }):
                config = load_config_from_yaml(f.name)
                
                assert config.project_endpoint == "https://foundry.azure.com"
                assert config.knowledge.search_endpoint == "https://search.azure.com"
        
        os.unlink(f.name)

    def test_env_variable_with_default(self):
        """Environment variables with default syntax should work."""
        yaml_content = """
project:
  name: default-test
  project_endpoint: ${NONEXISTENT_VAR:-https://default.endpoint.com}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            # Remove the var if it exists
            env_backup = os.environ.pop("NONEXISTENT_VAR", None)
            try:
                config = load_config_from_yaml(f.name)
                assert config.project_endpoint == "https://default.endpoint.com"
            finally:
                if env_backup:
                    os.environ["NONEXISTENT_VAR"] = env_backup
        
        os.unlink(f.name)

    def test_tools_config_normalization(self):
        """Tools config should be normalized from nested structure."""
        yaml_content = """
project:
  name: tools-test

tools:
  enabled: true
  allowlist:
    - create_incident
    - add_comment

guardrails:
  pii_mode: detect
  content_safety_mode: standard
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            config = load_config_from_yaml(f.name)
            
            assert "create_incident" in config.tools_allowed
            assert "add_comment" in config.tools_allowed
            assert config.governance.pii_mode == "detect"
            assert config.governance.content_safety_mode == "standard"
        
        os.unlink(f.name)


class TestConfigValidation:
    """Test configuration validation."""

    def test_invalid_mode_rejected(self):
        """Invalid loop mode should raise validation error."""
        yaml_content = """
project:
  name: invalid-test
workflow:
  default_mode: invalid_mode
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            with pytest.raises(Exception):  # Pydantic validation error
                load_config_from_yaml(f.name)
        
        os.unlink(f.name)
