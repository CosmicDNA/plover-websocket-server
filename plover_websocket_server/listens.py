from asyncio import Task, create_task, gather
from asyncio.futures import Future

from plover import log


# Listens interface
class Listens:
    _listeners: list[callable]
    _status: any
    _count: int

    async def _notify_listeners(self, new_status) -> Future:
        pass

    def add_listener(self, callback: callable) -> None:
        pass

    def stop_listening(self) -> None:
        pass


class RawListens:
    def __get__(self, obj: Listens, objtype=None):
        value = obj._status
        # log.debug(f'Accessing status giving {value}')
        return value

    def __set__(self, obj: Listens, value):
        # log.debug(f'Updating status to {value}')
        obj._status = value
        if len(obj._listeners):
            name = f"NL-{obj._count}"
            log.debug(f"Creating {name} with value {value}...")
            create_task(obj._notify_listeners(value), name=name)
            obj._count = obj._count + 1


class Listens:
    _listeners: list[callable]
    status: RawListens = RawListens()
    _count: int = 0

    def __init__(self) -> None:
        self._listeners = []

    async def _notify_listeners(self, new_status) -> Future:
        # Create a list of coroutines to execute concurrently
        coroutines = [listener(new_status) for listener in self._listeners]
        return gather(*coroutines)

    def add_listener(self, callback: callable) -> None:
        self._listeners.append(callback)

    def stop_listening(self) -> None:
        self._listeners = []
