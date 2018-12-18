""" Define a decorator that protects against too many calls in short time. """

import asyncio
import time
from typing import Iterable, Callable, Any, Dict


class _Data:
    """ Data storage for steady decorator."""

    def __init__(self, min_cycle_duration: int) -> None:
        """ Initialize this Data structure. """
        self.last_update_attempt = 0
        self.min_cycle_duration = min_cycle_duration

    def update(self, timestamp=None) -> None:
        """ Update the latest call timestamp.

        Usually call to this function is not needed, especially if hass is
        the only entity that can change the protected state. Sometimes
        the state may be changed from outside bypassing the decorator, for
        example a user used manual light switch. In such case we want record
        new change attempt so it would not be overriden by a waiting call.

        In reall life it means that this method should be called on a state.
        """
        if timestamp is None:
            self.last_update_attempt = time.time()
        elif self.last_update_attempt < timestamp:
            self.last_update_attempt = timestamp


def steady(functions_to_protect: Iterable[str],
           min_cycle_duration: int = 15) -> Callable[[Any], Any]:
    """ Async class decorator protecting against abusive calls count.

    The decorator doesn't allow to execute more then one call in some
    predefined amount of time. Every consecutive call will be delayed and
    potentially skipped. If too many calls are executed in short period
    of time, only the last one will be processed

    The decorator should be instantiated on async, non-static methods only.

    The decorator is useful to protect light bulbs and heater, as they may
    break down if are switched off and on constantly in a tight loop, which
    could happen for many reasons.

    The decorator, through 'functions_to_protect', accepts a list of method
    names on which it would install steady decorator. These method are bound
    together.

    min_cycle_duration is minimum amount of time in seconds in which the
    decorated method can be called again.
    """

    def decorator(cls) -> Any:
        class SteadyDecorated(cls):
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                decorator_data = _Data(min_cycle_duration)
                self._steady_decorator = decorator_data
                function = None
                for function_name in functions_to_protect:
                    function = getattr(cls, function_name, None)
                    assert function, "Given class '%s' has no '%s' method" \
                        % (cls, function_name)

                    async def steady_function(*args, **kwargs):
                        this_update_attempt = time.time()
                        time_to_wait = decorator_data.last_update_attempt + \
                            decorator_data.min_cycle_duration - \
                            this_update_attempt
                        decorator_data.update(this_update_attempt)
                        if time_to_wait > 0:
                            await asyncio.sleep(time_to_wait)
                        if decorator_data.last_update_attempt == this_update_attempt:
                            return await function(self, *args, **kwargs)

                    setattr(self, function_name, steady_function)
        return SteadyDecorated
    return decorator
