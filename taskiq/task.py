import asyncio
from time import time
from typing import TYPE_CHECKING, Generic, TypeVar

from taskiq.exceptions import (
    ResultGetError,
    ResultIsReadyError,
    TaskiqResultTimeoutError,
)

if TYPE_CHECKING:
    from taskiq.abc.result_backend import AsyncResultBackend
    from taskiq.result import TaskiqResult

_ReturnType = TypeVar("_ReturnType")


class AsyncTaskiqTask(Generic[_ReturnType]):
    """AsyncTask for AsyncResultBackend."""

    def __init__(
        self,
        task_id: str,
        result_backend: "AsyncResultBackend[_ReturnType]",
    ) -> None:
        self.task_id = task_id
        self.result_backend = result_backend

    async def is_ready(self) -> bool:
        """
        Checks if task is completed.

        :raises ResultIsReadyError: if we can't get info about task readyness.

        :return: True if task is completed.
        """
        try:
            return await self.result_backend.is_result_ready(self.task_id)
        except Exception as exc:
            raise ResultIsReadyError() from exc

    async def get_result(self, with_logs: bool = False) -> "TaskiqResult[_ReturnType]":
        """
        Get result of a task from result backend.

        :param with_logs: whether you want to fetch logs from worker.

        :raises ResultGetError: if we can't get result from ResultBackend.

        :return: task's return value.
        """
        try:
            return await self.result_backend.get_result(
                self.task_id,
                with_logs=with_logs,
            )
        except Exception as exc:
            raise ResultGetError() from exc

    async def wait_result(
        self,
        check_interval: float = 1.0,
        timeout: float = 5.0,
        with_logs: bool = False,
    ) -> "TaskiqResult[_ReturnType]":
        """
        Waits until result is ready.

        This method just checks whether the task is
        ready. And if it is it returns the result.

        It may throw TaskiqResultTimeoutError if
        task didn't became ready in provided
        period of time.

        :param check_interval: How often checks are performed.
        :param timeout: timeout for the result.
        :param with_logs: whether you want to fetch logs from worker.
        :raises TaskiqResultTimeoutError: if task didn't
            become ready in provided period of time.
        :return: task's return value.
        """
        start_time = time()
        while not await self.is_ready():
            await asyncio.sleep(check_interval)
            if time() - start_time > timeout:
                raise TaskiqResultTimeoutError()
        return await self.get_result(with_logs=with_logs)
