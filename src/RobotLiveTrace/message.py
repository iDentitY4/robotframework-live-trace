from typing import Any, TypedDict


class Message(TypedDict):
    action: str
    data: dict[str, Any] | None
    result: dict[str, Any] | None
