from ..knowledge.connector import AsyncFoundryConnector
import json

class FoundrySearchTool:
    def __init__(self, config):
        self.connector = AsyncFoundryConnector(config.search_endpoint, config.index_name)

    def get_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "search_enterprise_knowledge",
                "description": "Searches Foundry IQ for documents.",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}
            }
        }

    async def execute(self, query: str) -> str:
        results = await self.connector.search(query)
        return json.dumps([c.model_dump() for c in results])