from fastapi import APIRouter, HTTPException
from infrastructure.task_delegator import TaskDelegator
from core.flag_manager import FlagManager
from pydantic import BaseModel
from typing import List, Any

class TaskResponse(BaseModel):
    id: str
    message: str

class TaskRouter:
    def __init__(self, task_delegator: TaskDelegator):
        self.task_delegator = task_delegator

    def get_router(self):
        router = APIRouter(prefix="/tasks", tags=["tasks"])

        @router.get("/", response_model=List[TaskResponse])
        async def get_pending_tasks():
            """Returns all currently pending manual tasks."""
            return [
                {"id": t.id, "message": t.message} 
                for t in self.task_delegator._tasks.values()
            ]

        @router.post("/{task_id}/resolve")
        async def resolve_task(task_id: str):
            """Marks a manual task as completed."""
            if task_id not in self.task_delegator._tasks:
                raise HTTPException(status_code=404, detail="Task not found")
            
            self.task_delegator.resolve_task(task_id)
            return {"status": "success"}

        return router

class FlagRouter:
    def __init__(self, flag_manager: FlagManager):
        self.flag_manager = flag_manager

    def get_router(self):
        router = APIRouter(prefix="/flags", tags=["flags"])

        @router.get("/")
        async def get_all_flags():
            return self.flag_manager.get_all_flags()

        @router.post("/{flag_id}")
        async def set_flag(flag_id: int, value: int):
            self.flag_manager.set_flag(flag_id, value)
            return {"status": "success"}

        return router

class InfrastructureRouter:
    def __init__(self, prdms: "PRDMS4"):
        self.prdms = prdms

    def get_router(self):
        router = APIRouter(prefix="/infra", tags=["infrastructure"])
        router.include_router(TaskRouter(self.prdms._task_delegator).get_router())
        router.include_router(FlagRouter(self.prdms._flag_manager).get_router())
        return router
