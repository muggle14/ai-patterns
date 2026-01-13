from typing import Dict, Any
from .logic_app import LogicAppTool
from .foundry_search import FoundrySearchTool
from ..config import AgentConfig

class ToolRegistry:
    _tools = {}

    @classmethod
    def register_defaults(cls, config: AgentConfig):
        if config.knowledge.enabled:
            cls._tools["foundry_search"] = FoundrySearchTool(config.knowledge)

        for la in config.logic_apps:
            cls._tools[la.name] = LogicAppTool(la.name, la.endpoint_url)

    @classmethod
    def get_definitions(cls):
        return [t.get_definition() for t in cls._tools.values()]