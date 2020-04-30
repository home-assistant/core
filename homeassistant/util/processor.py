"""Processor util methods."""
import asyncio
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Generic, Iterable, List, Optional, TypeVar, cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

DEFAULT_BACKGROUND_RETRY_INTERVAL = timedelta(minutes=5)
DEFAULT_BACKGROUND_TIMEOUT_ATTEMPTS = 3
DEFAULT_BACKGROUND_RUN_IN_PARALLEL = True
DEFAULT_FOREGROUND_RETRY_INTERVAL = timedelta(milliseconds=300)
DEFAULT_FOREGROUND_TIMEOUT_ATTEMPTS = 3

BgOriginalObjectType = TypeVar("BgOriginalObjectType")
BgNewObjectType = TypeVar("BgNewObjectType")
BgProcessFunctionReturnType = TypeVar("BgProcessFunctionReturnType")

BgObjectsType = Iterable[BgOriginalObjectType]
BgMapFunctionType = Callable[
    [HomeAssistant, BgOriginalObjectType], Awaitable[BgNewObjectType]
]
BgProcessFunctionType = Callable[[HomeAssistant, BgNewObjectType], Awaitable[None]]
BgCancelFunctionType = Callable[[], None]

FgProcessFunctionReturnType = TypeVar("FgProcessFunctionReturnType")


class MapObjectResult(Generic[BgOriginalObjectType, BgNewObjectType]):
    """The result of processing an object in async_background_add_entities_retry."""

    def __init__(
        self,
        original_object: BgOriginalObjectType,
        new_object: BgNewObjectType,
        success: bool,
    ) -> None:
        """Initialize the object."""
        self._original_object = original_object
        self._new_object = new_object
        self._success = success

    @property
    def original_object(self) -> BgOriginalObjectType:
        """Return the original object value."""
        return self._original_object

    @property
    def new_object(self) -> BgNewObjectType:
        """Return the new object value."""
        return self._new_object

    @property
    def success(self) -> bool:
        """Return the success value."""
        return self._success


async def async_background_add_entities_retry(
    hass: HomeAssistant,
    objects: BgObjectsType,
    map_function: BgMapFunctionType,
    async_add_entities: Callable[..., Awaitable[None]],
    retry_interval: timedelta = DEFAULT_BACKGROUND_RETRY_INTERVAL,
    timeout_attempts: int = DEFAULT_BACKGROUND_TIMEOUT_ATTEMPTS,
    run_in_parallel: bool = DEFAULT_BACKGROUND_RUN_IN_PARALLEL,
    update_before_add: Optional[bool] = None,
) -> BgCancelFunctionType:
    """Asynchronously create and add entities with retries.

    :param hass: The current home assistant instance.
    :param objects: The objects to map.
    :param map_function: Maps the original object to a new object. Note: Throwing an exception or returning None from this function results in the original object being retried later.
    :param async_add_entities: The same function provided to a platform's async_setup_entry function.
    :param retry_interval: Time between attempts to map and process objects.
    :param timeout_attempts: Number of attempts before giving up. A value of 0 means it runs forever.
    :param run_in_parallel: When True, objects will be handled in parallel. (Default: True)
    :param update_before_add: Passed as argument to async_add_entities.
    :return: A function that can be used to cancel future object processing.
    """

    async def async_process_entity(hass: HomeAssistant, entity: Entity) -> None:
        await async_add_entities([entity], update_before_add=update_before_add)

    return await async_background_map_retry(
        hass,
        objects,
        map_function,
        async_process_entity,
        retry_interval,
        timeout_attempts,
        run_in_parallel,
    )


async def async_background_map_retry(
    hass: HomeAssistant,
    objects: BgObjectsType,
    map_function: BgMapFunctionType,
    process_function: BgProcessFunctionType,
    retry_interval: timedelta = DEFAULT_BACKGROUND_RETRY_INTERVAL,
    timeout_attempts: int = DEFAULT_BACKGROUND_TIMEOUT_ATTEMPTS,
    run_in_parallel: bool = DEFAULT_BACKGROUND_RUN_IN_PARALLEL,
) -> BgCancelFunctionType:
    """Asynchronously map and process objects with retries.

    :param hass: The current home assistant instance.
    :param objects: The objects to map.
    :param map_function: Maps the original object to a new object. Note: Throwing an exception or returning None from this function results in the original object being retried later.
    :param process_function: Processes the new object once it was successful mapped.
    :param retry_interval: Time between attempts to map and process objects.
    :param timeout_attempts: Number of attempts before giving up. A value of 0 means it runs forever.
    :param run_in_parallel: When True, objects will be handled in parallel. (Default: True)
    :return: A function that can be used to cancel future object processing.
    """
    original_objects = list(objects)
    attempt_count = 0
    cancel_func1 = cast(Callable, None)

    @callback
    def cancel() -> None:
        nonlocal cancel_func1
        cancel_func1()

    async def map_object(original_object: BgOriginalObjectType) -> MapObjectResult:
        try:
            new_object = await map_function(hass, original_object)
            if new_object is None:
                raise Exception("Failed to map object.")

            await process_function(hass, new_object)
            return MapObjectResult(
                original_object=original_object, new_object=new_object, success=True
            )

        except Exception:  # pylint: disable=broad-except
            return MapObjectResult(
                original_object=original_object, new_object=None, success=False
            )

    @callback
    async def map_objects(now: Optional[datetime] = None) -> None:
        nonlocal original_objects, attempt_count, run_in_parallel
        attempt_count += 1

        # Process objects in parallel.
        if run_in_parallel:
            results: List[MapObjectResult] = await asyncio.gather(
                *[
                    map_object(original_object)
                    for original_object in tuple(original_objects)
                ],
                loop=hass.loop,
            )
        # Process objects serially.
        else:
            results = [
                await map_object(original_object)
                for original_object in tuple(original_objects)
            ]

        # Remove processed objects.
        for result in results:
            if result.success:
                original_objects.remove(result.original_object)

        # Determine if we've finished processing objects.
        if not original_objects or attempt_count >= timeout_attempts > 0:
            cancel()

    # Schedule the retry interval.
    cancel_func1 = async_track_time_interval(hass, map_objects, retry_interval)

    # Attempt to add the objects.
    await map_objects()

    return cancel


async def async_foreground_retry(
    hass: HomeAssistant,
    process_function: Callable[..., FgProcessFunctionReturnType],
    timeout_attempts: int = DEFAULT_FOREGROUND_TIMEOUT_ATTEMPTS,
    retry_interval: timedelta = DEFAULT_FOREGROUND_RETRY_INTERVAL,
) -> FgProcessFunctionReturnType:
    """Call a function with a retry in the event it failed.

    This is a wrapper for process_function to allow the process_function to be
    re-ran if it raised an exception. If process_function fails consistently,
    the last exception raised by process_function will be raised. If
    process_function does not raise an exception, it's return value will be
    immediately returned.
    """
    last_exception: Exception = cast(Exception, None)
    for attempt in range(1, timeout_attempts + 1):
        try:
            return await hass.async_add_executor_job(process_function)
        except Exception as ex:  # pylint: disable=broad-except
            last_exception = ex
            if attempt < timeout_attempts:
                await asyncio.sleep(retry_interval.total_seconds())

    raise last_exception
