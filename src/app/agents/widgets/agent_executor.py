# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""AgentExecutor for WidgetsMCPAgent, handles streaming and event queue updates."""

import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import (
    Message,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a.utils import new_agent_text_message, new_task, new_text_artifact

from app.agents.widgets.agent import WidgetsMCPAgent  # type: ignore[import-untyped]
from app.settings import AppSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPAgentExecutor(AgentExecutor):
    """
    A WidgetsMCPAgent agent executor.

    Initialize the MCPAgentExecutor with the provided settings.

    Args:
        settings: Application settings used to construct the WidgetsMCPAgent.
    """

    def __init__(self, settings: AppSettings):
        self.agent = WidgetsMCPAgent(settings)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Executes the agent task.

        The task is executed based on the provided request context and manages event
        updates via the event queue.

        Args:
            context: The context containing user input and current task information.
            event_queue: The event queue used to enqueue task-related events.


        """
        query = context.get_user_input()
        task = context.current_task

        if not task:
            assert isinstance(context.message, Message)
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        async for item in self.agent.stream(query, task.context_id):
            is_task_complete = item["is_task_complete"]
            require_user_input = item["require_user_input"]
            content = item["content"]

            logger.info(
                f"Stream item received: complete={is_task_complete},"
                f" require_input={require_user_input}, content_len={len(content)}"
            )

            if not is_task_complete and not require_user_input:
                await event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        status=TaskStatus(
                            state=TaskState.working,
                            message=new_agent_text_message(
                                content,
                                task.context_id,
                                task.id,
                            ),
                        ),
                        final=False,
                        context_id=task.context_id,
                        task_id=task.id,
                    )
                )
            elif require_user_input:
                await event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        status=TaskStatus(
                            state=TaskState.input_required,
                            message=new_agent_text_message(
                                content,
                                task.context_id,
                                task.id,
                            ),
                        ),
                        final=True,
                        context_id=task.context_id,
                        task_id=task.id,
                    )
                )
            else:
                await event_queue.enqueue_event(
                    TaskArtifactUpdateEvent(
                        append=False,
                        context_id=task.context_id,
                        task_id=task.id,
                        last_chunk=True,
                        artifact=new_text_artifact(
                            name="current_result",
                            description="Result of request to agent.",
                            text=content,
                        ),
                    )
                )
                await event_queue.enqueue_event(
                    TaskStatusUpdateEvent(
                        status=TaskStatus(state=TaskState.completed),
                        final=True,
                        context_id=task.context_id,
                        task_id=task.id,
                    )
                )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """
        Attempts to cancel the current agent execution.

        Args:
            context: The request context for the operation.
            event_queue: The event queue associated with the execution.

        Raises:
            Exception: Always raised to indicate that cancellation is not supported.
        """
        raise Exception("cancel not supported")
