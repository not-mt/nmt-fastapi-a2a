# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""AgentExecutor for DirectorAgent, handles streaming and event queue updates."""

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

from app.agents.director.agent import DirectorAgent
from app.settings import AppSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DirectorAgentExecutor(AgentExecutor):
    """
    The DirectorAgent executor.

    Initialize the DirectorAgentExecutor.

    Args:
        settings: Application settings used to construct the DirectorAgent.
    """

    def __init__(self, settings: AppSettings):
        self.agent = DirectorAgent(settings)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Executes the agent task workflow based on the provided context and event queue.

        This asynchronous method processes user input and manages task execution by
        streaming agent responses. It updates the event queue with task status and
        artifacts according to the agent's output.

        Args:
            context: The current request context containing user input and task
                information.
            event_queue: The event queue to which task status and artifact updates
                are enqueued.


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
                f" content={content}"
            )

            if not is_task_complete and not require_user_input:
                logger.info(f"Task {task.id} is not complete.")
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
                logger.info(f"Task {task.id} needs user input!")
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
                logger.info(f"Task {task.id} completed.")
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
        Cancels the current operation.

        Args:
            context: The request context for the operation.
            event_queue: The event queue associated with the operation.

        Raises:
            Exception: Always raised to indicate that cancellation is not supported.
        """
        raise Exception("cancel not supported")
