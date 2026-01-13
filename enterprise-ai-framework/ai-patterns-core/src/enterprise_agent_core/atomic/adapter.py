"""Azure AI Foundry Atomic Agent Adapter.

Provides integration with Azure AI Foundry Agents (Assistants API)
as specialized skills within the Actor-Critic engine.

This adapter handles:
- Thread and message management
- Run creation and polling
- requires_action handling for tool calls
- Tool result submission back to Foundry
- Response extraction with citations

IMPORTANT: This uses preview Azure AI SDK APIs.
Pin azure-ai-projects version in requirements.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from ..standards import beta

logger = logging.getLogger(__name__)

# Maximum iterations for requires_action loop (safety limit)
MAX_TOOL_ITERATIONS = 10

# Polling interval for run status
POLL_INTERVAL_SECONDS = 0.5


@dataclass
class ToolResult:
    """Result from a tool execution."""
    tool_call_id: str
    output: str
    success: bool = True


@dataclass
class AtomicAgentResponse:
    """Response from atomic agent processing."""
    content: str
    citations: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls_made: List[str] = field(default_factory=list)
    run_id: str = ""
    status: str = "completed"


@beta(since="0.1.5")
class AzureAtomicAdapter:
    """Azure AI Foundry Agent adapter for atomic agent skills.
    
    Implements the full Foundry run loop including:
    - Message submission
    - Run creation and polling
    - requires_action handling for function tools
    - Tool result submission
    - Response extraction
    
    Usage:
        adapter = AzureAtomicAdapter(
            client=project_client,
            agent_id="asst_XXX",
            tool_executor=my_tool_executor,
        )
        response = await adapter.process_turn("Create a ticket", thread_id)
    """

    def __init__(
        self,
        client: Any,  # AIProjectClient
        agent_id: str,
        tool_executor: Optional[Callable] = None,
        max_iterations: int = MAX_TOOL_ITERATIONS,
    ):
        """Initialize the adapter.
        
        Args:
            client: Azure AI Projects client (AIProjectClient)
            agent_id: Foundry Agent/Assistant ID
            tool_executor: Async function to execute tools: (name, args) -> result
            max_iterations: Maximum tool call iterations (safety limit)
        """
        self.client = client
        self.agent_id = agent_id
        self.tool_executor = tool_executor
        self.max_iterations = max_iterations

    async def process_turn(
        self,
        user_input: str,
        thread_id: str,
        additional_instructions: Optional[str] = None,
    ) -> AtomicAgentResponse:
        """Process a conversation turn through the Foundry agent.
        
        Args:
            user_input: User message content
            thread_id: Foundry thread ID
            additional_instructions: Optional per-run instructions
            
        Returns:
            AtomicAgentResponse with content and metadata
        """
        try:
            # Import Foundry types
            from azure.ai.projects.models import RunStatus
        except ImportError:
            logger.error("azure-ai-projects not installed")
            return AtomicAgentResponse(
                content="Error: azure-ai-projects SDK not installed",
                status="failed"
            )

        tool_calls_made = []

        # 1. Add user message to thread
        await self.client.agents.create_message(
            thread_id=thread_id,
            role="user",
            content=user_input,
        )
        logger.info(f"Added message to thread {thread_id}")

        # 2. Create run
        run_params = {
            "thread_id": thread_id,
            "agent_id": self.agent_id,
        }
        if additional_instructions:
            run_params["additional_instructions"] = additional_instructions

        run = await self.client.agents.create_run(**run_params)
        logger.info(f"Created run {run.id} for agent {self.agent_id}")

        # 3. Poll and handle requires_action
        iterations = 0
        terminal_statuses = {
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.EXPIRED,
        }

        while run.status not in terminal_statuses:
            if iterations >= self.max_iterations:
                logger.error(f"Max iterations ({self.max_iterations}) reached")
                return AtomicAgentResponse(
                    content="Error: Maximum tool iterations exceeded",
                    run_id=run.id,
                    status="max_iterations",
                    tool_calls_made=tool_calls_made,
                )

            # Check for requires_action (tool calls)
            if run.status == RunStatus.REQUIRES_ACTION:
                tool_results = await self._handle_requires_action(run, thread_id)
                tool_calls_made.extend([r.tool_call_id for r in tool_results])

                # Submit tool results
                run = await self.client.agents.submit_tool_outputs_to_run(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=[
                        {"tool_call_id": r.tool_call_id, "output": r.output}
                        for r in tool_results
                    ],
                )
                logger.info(f"Submitted {len(tool_results)} tool outputs")
            else:
                # Wait and poll
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                run = await self.client.agents.get_run(
                    thread_id=thread_id,
                    run_id=run.id,
                )

            iterations += 1

        # 4. Handle terminal status
        if run.status == RunStatus.FAILED:
            error_msg = getattr(run, "last_error", {})
            logger.error(f"Run failed: {error_msg}")
            return AtomicAgentResponse(
                content=f"Agent run failed: {error_msg}",
                run_id=run.id,
                status="failed",
                tool_calls_made=tool_calls_made,
            )

        if run.status in {RunStatus.CANCELLED, RunStatus.EXPIRED}:
            return AtomicAgentResponse(
                content=f"Run {run.status.value}",
                run_id=run.id,
                status=run.status.value,
                tool_calls_made=tool_calls_made,
            )

        # 5. Extract response
        return await self._extract_response(thread_id, run.id, tool_calls_made)

    async def _handle_requires_action(
        self,
        run: Any,
        thread_id: str,
    ) -> List[ToolResult]:
        """Handle requires_action by executing tool calls.
        
        Args:
            run: The run object with required_action
            thread_id: Thread ID for logging
            
        Returns:
            List of ToolResult with outputs
        """
        results = []

        # Extract tool calls from run
        required_action = getattr(run, "required_action", None)
        if not required_action:
            return results

        submit_outputs = getattr(required_action, "submit_tool_outputs", None)
        if not submit_outputs:
            return results

        tool_calls = getattr(submit_outputs, "tool_calls", [])

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            tool_args_str = tool_call.function.arguments
            tool_call_id = tool_call.id

            logger.info(f"Executing tool: {tool_name} (call_id: {tool_call_id})")

            try:
                # Parse arguments
                tool_args = json.loads(tool_args_str) if tool_args_str else {}

                # Execute tool
                if self.tool_executor:
                    output = await self.tool_executor(tool_name, tool_args)
                    if isinstance(output, dict):
                        output = json.dumps(output)
                    results.append(ToolResult(
                        tool_call_id=tool_call_id,
                        output=str(output),
                        success=True,
                    ))
                else:
                    # No executor provided
                    results.append(ToolResult(
                        tool_call_id=tool_call_id,
                        output=json.dumps({
                            "error": "No tool executor configured",
                            "tool": tool_name,
                        }),
                        success=False,
                    ))
                    logger.warning(f"No tool executor for {tool_name}")

            except Exception as e:
                logger.error(f"Tool {tool_name} failed: {e}")
                results.append(ToolResult(
                    tool_call_id=tool_call_id,
                    output=json.dumps({"error": str(e)}),
                    success=False,
                ))

        return results

    async def _extract_response(
        self,
        thread_id: str,
        run_id: str,
        tool_calls_made: List[str],
    ) -> AtomicAgentResponse:
        """Extract the agent's response from the thread.
        
        Args:
            thread_id: Thread ID
            run_id: Completed run ID
            tool_calls_made: List of tool call IDs executed
            
        Returns:
            AtomicAgentResponse with content and citations
        """
        messages = await self.client.agents.list_messages(thread_id=thread_id)

        # Find the latest assistant message
        for message in messages.data:
            if message.role == "assistant":
                content_parts = message.content
                if content_parts and len(content_parts) > 0:
                    text_content = content_parts[0]

                    # Extract text value
                    content = ""
                    if hasattr(text_content, "text"):
                        content = text_content.text.value
                    elif hasattr(text_content, "value"):
                        content = text_content.value
                    else:
                        content = str(text_content)

                    # Extract annotations/citations if present
                    citations = []
                    if hasattr(text_content, "text") and hasattr(text_content.text, "annotations"):
                        for annotation in text_content.text.annotations:
                            citation = {
                                "type": annotation.type,
                                "text": getattr(annotation, "text", ""),
                            }
                            if hasattr(annotation, "file_citation"):
                                citation["file_id"] = annotation.file_citation.file_id
                            citations.append(citation)

                    return AtomicAgentResponse(
                        content=content,
                        citations=citations,
                        tool_calls_made=tool_calls_made,
                        run_id=run_id,
                        status="completed",
                    )

        # No assistant message found
        return AtomicAgentResponse(
            content="No response generated",
            run_id=run_id,
            status="no_response",
            tool_calls_made=tool_calls_made,
        )

    async def create_thread(self) -> str:
        """Create a new thread.
        
        Returns:
            Thread ID
        """
        thread = await self.client.agents.create_thread()
        logger.info(f"Created thread: {thread.id}")
        return thread.id