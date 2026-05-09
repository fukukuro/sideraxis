import asyncio
import uuid
from typing import Dict, List, Any


class Task:
    """
    Represents a task that needs to be performed manually by a human.
    """

    def __init__(self, task_id: str, message: str):
        self.id = task_id
        self.message = message
        self.future: asyncio.Future[Any] = asyncio.Future()


class TaskDelegator:
    """
    Manages manual tasks, allowing asynchronous waiting for human intervention.
    """

    def __init__(self):
        # Dictionary to store tasks by their unique ID
        self._tasks: Dict[str, Task] = {}

    async def issue_task_and_wait(self, message: str) -> Any:
        """
        Issues a new manual task and waits asynchronously for its completion.

        Args:
            message: Instructions for the human operator.

        Returns:
            Any: The result or data passed when the task was completed.
        """
        task_id = str(uuid.uuid4())[:8]  # Short unique ID
        task = Task(task_id, message)
        self._tasks[task_id] = task

        print(f"[ManualTask] Issued: {message} (ID: {task_id})")

        try:
            # Wait until someone calls complete_task(task_id)
            return await task.future
        finally:
            # Cleanup task after completion, cancellation, or error
            if task_id in self._tasks:
                del self._tasks[task_id]

    def complete_task(self, task_id: str, result: Any = None) -> bool:
        """
        Marks a manual task as completed from an external source (e.g., UI).

        Args:
            task_id: The ID of the task to complete.
            result: Optional data to return to the requester.

        Returns:
            bool: True if the task was found and completed, False otherwise.
        """
        task = self._tasks.get(task_id)
        if task and not task.future.done():
            task.future.set_result(result)
            print(f"[ManualTask] Completed: ID {task_id}")
            return True
        return False

    def get_pending_tasks(self) -> List[Dict[str, str]]:
        """
        Returns a list of currently pending manual tasks.
        Used by the UI to display instructions to the user.
        """
        return [
            {"id": task.id, "message": task.message} for task in self._tasks.values()
        ]
