"""Prompt loader for loading and managing prompt templates.

Supports loading prompts from:
1. Standard prompts (built into the package)
2. Project prompts directory (both .txt files and Python modules)
3. Custom overrides (passed at runtime)

Python module support:
- Looks for __init__.py in the prompts directory
- Loads variables like SYSTEM_PROMPT, DOMAIN_PROMPT, STYLE_PROMPT, TOOL_INSTRUCTIONS
"""

import os
import sys
import hashlib
import logging
import importlib.util
from typing import Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Known prompt variable names to extract from Python modules
KNOWN_PROMPT_VARS = [
    "SYSTEM_PROMPT",
    "DOMAIN_PROMPT",
    "STYLE_PROMPT",
    "TOOL_INSTRUCTIONS",
    "CRITIC_PROMPT",
    "PLANNER_PROMPT",
    "SYNTHESIZER_PROMPT",
]


@dataclass
class PromptPack:
    """Collection of prompts for an agent.

    Combines standard prompts with project-specific overrides.
    """

    name: str
    prompts: Dict[str, str] = field(default_factory=dict)
    versions: Dict[str, str] = field(default_factory=dict)
    hashes: Dict[str, str] = field(default_factory=dict)

    def get(self, prompt_name: str) -> Optional[str]:
        """Get a prompt by name."""
        return self.prompts.get(prompt_name)

    def get_version(self, prompt_name: str) -> Optional[str]:
        """Get the version of a prompt."""
        return self.versions.get(prompt_name)

    def get_hash(self, prompt_name: str) -> Optional[str]:
        """Get the hash of a prompt for audit."""
        return self.hashes.get(prompt_name)

    def format(self, prompt_name: str, **kwargs) -> Optional[str]:
        """Get and format a prompt with variables."""
        prompt = self.get(prompt_name)
        if prompt:
            return prompt.format(**kwargs)
        return None

    def get_all_hashes(self) -> Dict[str, str]:
        """Get all prompt hashes for audit logging."""
        return dict(self.hashes)


class PromptLoader:
    """Loader for prompt templates.

    Loads prompts from:
    1. Standard prompts (built-in)
    2. Project prompts directory (text files or Python modules)
    3. Custom overrides
    """

    def __init__(
        self,
        standard_prompts: Optional[Dict[str, str]] = None,
        project_prompts_dir: Optional[str] = None,
        custom_overrides: Optional[Dict[str, str]] = None,
    ):
        """Initialize the prompt loader.

        Args:
            standard_prompts: Built-in standard prompts
            project_prompts_dir: Directory containing project prompts
            custom_overrides: Runtime prompt overrides
        """
        self.standard_prompts = standard_prompts or {}
        self.project_prompts_dir = project_prompts_dir
        self.custom_overrides = custom_overrides or {}

    def load(self, pack_name: str = "default") -> PromptPack:
        """Load a complete prompt pack.

        Merges prompts in order (later overrides earlier):
        1. Standard prompts
        2. Project prompts from directory (text or Python)
        3. Custom overrides

        Args:
            pack_name: Name for the prompt pack

        Returns:
            PromptPack with all loaded prompts
        """
        prompts = {}
        versions = {}
        hashes = {}

        # Load standard prompts
        for name, content in self.standard_prompts.items():
            prompts[name] = content
            versions[name] = self._extract_version(name)
            hashes[name] = self._compute_hash(content)

        # Load project prompts from directory
        if self.project_prompts_dir and os.path.isdir(self.project_prompts_dir):
            # First try loading from Python module (__init__.py)
            self._load_from_python_module(prompts, versions, hashes)
            
            # Then load text files (they override Python module prompts)
            self._load_from_text_files(prompts, versions, hashes)

        # Apply custom overrides
        for name, content in self.custom_overrides.items():
            prompts[name] = content
            versions[name] = "custom"
            hashes[name] = self._compute_hash(content)
            logger.info(f"Applied custom prompt override: {name}")

        return PromptPack(
            name=pack_name,
            prompts=prompts,
            versions=versions,
            hashes=hashes,
        )

    def _load_from_python_module(
        self,
        prompts: Dict[str, str],
        versions: Dict[str, str],
        hashes: Dict[str, str],
    ) -> None:
        """Load prompts from a Python module in the prompts directory."""
        init_path = os.path.join(self.project_prompts_dir, "__init__.py")
        
        if not os.path.exists(init_path):
            return
        
        try:
            # Load the module dynamically
            spec = importlib.util.spec_from_file_location("project_prompts", init_path)
            if spec is None or spec.loader is None:
                return
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Extract known prompt variables
            for var_name in KNOWN_PROMPT_VARS:
                if hasattr(module, var_name):
                    content = getattr(module, var_name)
                    if isinstance(content, str):
                        # Convert VAR_NAME to var_name for consistency
                        prompt_name = var_name.lower()
                        prompts[prompt_name] = content
                        versions[prompt_name] = "project_v1"
                        hashes[prompt_name] = self._compute_hash(content)
                        logger.info(f"Loaded project prompt from module: {prompt_name}")
            
        except Exception as e:
            logger.warning(f"Failed to load prompts from Python module: {e}")

    def _load_from_text_files(
        self,
        prompts: Dict[str, str],
        versions: Dict[str, str],
        hashes: Dict[str, str],
    ) -> None:
        """Load prompts from text files in the prompts directory."""
        for filename in os.listdir(self.project_prompts_dir):
            if filename.endswith(".txt") or filename.endswith(".prompt"):
                name = os.path.splitext(filename)[0]
                filepath = os.path.join(self.project_prompts_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        content = f.read()
                    prompts[name] = content
                    versions[name] = self._extract_version(name)
                    hashes[name] = self._compute_hash(content)
                    logger.info(f"Loaded project prompt: {name}")
                except Exception as e:
                    logger.warning(f"Failed to load prompt {filename}: {e}")

    def _extract_version(self, prompt_name: str) -> str:
        """Extract version from prompt name (e.g., 'critic_sufficiency_v1' -> 'v1')."""
        parts = prompt_name.rsplit("_", 1)
        if len(parts) == 2 and parts[1].startswith("v"):
            return parts[1]
        return "v1"

    def _compute_hash(self, content: str) -> str:
        """Compute a short hash of prompt content for audit."""
        return hashlib.sha256(content.encode()).hexdigest()[:12]


def load_project_prompts(prompts_dir: str) -> PromptPack:
    """Convenience function to load prompts from a use-case directory.
    
    Args:
        prompts_dir: Path to the prompts directory (e.g., use-cases/confluence-bot/prompts)
        
    Returns:
        PromptPack with loaded prompts
    """
    loader = PromptLoader(project_prompts_dir=prompts_dir)
    return loader.load(pack_name=os.path.basename(os.path.dirname(prompts_dir)))

