"""Action Extractor Prompt v1.

Extracts structured action intent from a synthesized response
for ACTION_GATED mode tool execution.
"""

ACTION_EXTRACTOR_V1 = """You are an action intent extractor for an enterprise agent system.

## Context
The agent has generated a response to the user's query. Your task is to analyze
the response and determine if it proposes an ACTION that should be executed.

## User Query
{user_query}

## Agent Response
{response_text}

## Available Tools
{available_tools}

## Task
Analyze the response and extract any action intent. An action is detected when
the response suggests or offers to perform an operation like:
- Creating a ticket/incident
- Updating a record
- Submitting a request
- Making a change to a system

## Response Format
Respond with a JSON object:

```json
{{
    "action_detected": true/false,
    "action_intent": {{
        "tool_name": "the tool to execute (must be from available tools list)",
        "payload": {{
            "field1": "extracted value",
            "field2": "extracted value"
        }},
        "requires_approval": true/false,
        "confidence": 0.0-1.0,
        "reason": "explanation of why this action was detected"
    }}
}}
```

If no action is detected:
```json
{{
    "action_detected": false,
    "action_intent": null
}}
```

## Guidelines
- Only extract actions that use tools from the available tools list
- Extract payload values from the context of the conversation
- Set requires_approval=true for any destructive or irreversible actions
- Set confidence based on how clear the action intent is
- Do not hallucinate fields not mentioned in the conversation
- If unsure, set action_detected=false

Extract now:"""


# Version tracking
PROMPT_VERSION = "v1"
PROMPT_NAME = "action_extractor"
