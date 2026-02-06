from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


HandlerType = Callable[["Event"], None]


@dataclass
class Event:
    type: str
    data: Any = None


class SyncEventBus:
    """
    vnpy.event.EventEngine와 동일한 타입 기반 라우팅 패턴을 단순 동기 방식으로 제공.
    독립 프로젝트로 분리될 때도 동작하도록 fallback 용도로 사용한다.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[HandlerType]] = {}
        self._general_handlers: list[HandlerType] = []

    def register(self, type_: str, handler: HandlerType) -> None:
        self._handlers.setdefault(type_, [])
        if handler not in self._handlers[type_]:
            self._handlers[type_].append(handler)

    def register_general(self, handler: HandlerType) -> None:
        if handler not in self._general_handlers:
            self._general_handlers.append(handler)

    def put(self, event: Event) -> None:
        for handler in self._handlers.get(event.type, []):
            handler(event)
        for handler in self._general_handlers:
            handler(event)


def create_event_bus() -> tuple[Any, type[Event]]:
    """
    가능하면 vnpy EventEngine를 사용하고, 불가하면 동기 이벤트 버스로 fallback.
    """
    try:
        from vnpy.event import Event as VnpyEvent
        from vnpy.event import EventEngine as VnpyEventEngine

        engine = VnpyEventEngine(interval=1)
        engine.start()
        return engine, VnpyEvent
    except Exception:
        return SyncEventBus(), Event


def stop_event_bus(engine: Any) -> None:
    stop = getattr(engine, "stop", None)
    if callable(stop):
        stop()
