from dataclasses import asdict, is_dataclass
from logging import getLogger
from typing import TYPE_CHECKING, Any, Coroutine, Dict, Generic, TypeVar, overload
from uuid import uuid4

from pydantic import BaseModel
from typing_extensions import ParamSpec

from taskiq.exceptions import SendTaskError
from taskiq.message import TaskiqMessage
from taskiq.task import AsyncTaskiqTask

if TYPE_CHECKING:
    from taskiq.abc.broker import AsyncBroker

_T = TypeVar("_T")  # noqa: WPS111
_FuncParams = ParamSpec("_FuncParams")
_ReturnType = TypeVar("_ReturnType")

logger = getLogger("taskiq")


class AsyncKicker(Generic[_FuncParams, _ReturnType]):
    """Class that used to modify data before sending it to broker."""

    def __init__(
        self,
        task_name: str,
        broker: "AsyncBroker",
        labels: Dict[str, Any],
    ) -> None:
        self.task_name = task_name
        self.broker = broker
        self.labels = labels

    def with_label(
        self,
        label_name: str,
        value: Any,
    ) -> "AsyncKicker[_FuncParams, _ReturnType]":
        """
        Update one single label.

        This method is used to update
        task's labels before sending.

        :param label_name: name of the label to update.
        :param value: label's value.
        :return: kicker object with new labels.
        """
        self.labels[label_name] = value
        return self

    def with_labels(
        self,
        labels: Dict[str, Any],
    ) -> "AsyncKicker[_FuncParams, _ReturnType]":
        """
        Update function's labels before sending.

        :param labels: dict with new labels.
        :return: kicker with new labels.
        """
        self.labels.update(labels)
        return self

    def with_broker(
        self,
        broker: "AsyncBroker",
    ) -> "AsyncKicker[_FuncParams, _ReturnType]":
        """
        Replace broker for the function.

        This method can be used with
        shared tasks.

        :param broker: new broker instance.
        :return: Kicker with new broker.
        """
        self.broker = broker
        return self

    @overload
    async def kiq(  # noqa: D102
        self: "AsyncKicker[_FuncParams, Coroutine[Any, Any, _T]]",
        *args: _FuncParams.args,
        **kwargs: _FuncParams.kwargs,
    ) -> AsyncTaskiqTask[_T]:
        ...

    @overload
    async def kiq(  # noqa: D102
        self: "AsyncKicker[_FuncParams, _ReturnType]",
        *args: _FuncParams.args,
        **kwargs: _FuncParams.kwargs,
    ) -> AsyncTaskiqTask[_ReturnType]:
        ...

    async def kiq(
        self,
        *args: _FuncParams.args,
        **kwargs: _FuncParams.kwargs,
    ) -> Any:
        """
        This method sends function call over the network.

        It gets current broker and calls it's kick method,
        returning what it returns.

        :param args: function's arguments.
        :param kwargs: function's key word arguments.

        :raises SendTaskError: if we can't send task to the broker.

        :returns: taskiq task.
        """
        logger.debug(
            f"Kicking {self.task_name} with args={args} and kwargs={kwargs}.",
        )
        message = self._prepare_message(*args, **kwargs)
        try:
            await self.broker.kick(self.broker.formatter.dumps(message, self.labels))
        except Exception as exc:
            raise SendTaskError() from exc
        return self.broker.result_backend.generate_task(message.task_id)

    @classmethod
    def _prepare_arg(cls, arg: Any) -> Any:
        """
        Parses argument if possible.

        This function is used to construct dicts
        from pydantic models or dataclasses.

        :param arg: argument to format.
        :return: Formatted argument.
        """
        if isinstance(arg, BaseModel):
            arg = arg.dict()
        if is_dataclass(arg):
            arg = asdict(arg)
        return arg

    def _prepare_message(  # noqa: WPS210
        self,
        *args: Any,
        **kwargs: Any,
    ) -> TaskiqMessage:
        """
        Create a message from args and kwargs.

        :param args: function's args.
        :param kwargs: function's kwargs.
        :return: constructed message.
        """
        formatted_args = []
        formatted_kwargs = {}
        for arg in args:
            formatted_args.append(self._prepare_arg(arg))
        for kwarg_name, kwarg_val in kwargs.items():
            formatted_kwargs[kwarg_name] = self._prepare_arg(kwarg_val)

        task_id = uuid4().hex

        return TaskiqMessage(
            task_id=task_id,
            task_name=self.task_name,
            meta=self.labels,
            args=formatted_args,
            kwargs=formatted_kwargs,
        )
