import aiohttp
import json

class LogicAppTool:
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url

    def get_definition(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": "Executes a Logic App workflow.",
                "parameters": {"type": "object", "properties": {"payload": {"type": "object"}}}
            }
        }

    async def execute(self, payload: dict) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, json=payload) as response:
                return await response.text()