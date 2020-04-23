"""Processor util methods."""
import asyncio
from datetime import timedelta
from typing import Awaitable, Callable, Iterable, List, NamedTuple, TypeVar

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

OriginalObjectType = TypeVar("OriginalObjectType")
NewObjectType = TypeVar("NewObjectType")
ObjectsType = Iterable[OriginalObjectType]
MapFunctionType = Callable[
    [HomeAssistant, OriginalObjectType], Awaitable[NewObjectType]
]
ProcessFunctionType = Callable[[HomeAssistant, NewObjectType], Awaitable]
CancelFunctionType = Callable[[], None]


class MapObjectResult(NamedTuple):
    """The result of processing an object in async_add_entities_retry."""

    original_object: OriginalObjectType
    new_object: NewObjectType
    success: bool


DEFAULT_RETRY_INTERVAL = timedelta(minutes=5)
DEFAULT_TIMEOUT_ATTEMPTS = 0
DEFAULT_RUN_IN_PARALLEL = True


async def async_add_entities_retry(
    hass: HomeAssistant,
    objects: ObjectsType,
    map_function: MapFunctionType,
    async_add_entities: Callable[[Iterable[Entity]], Awaitable[None]],
    retry_interval: timedelta = DEFAULT_RETRY_INTERVAL,
    timeout_attempts: int = DEFAULT_TIMEOUT_ATTEMPTS,
    run_in_parallel: bool = DEFAULT_RUN_IN_PARALLEL,
    update_before_add: bool = None,
) -> CancelFunctionType:
    """Asynchronously create and add entities with retries.

    :param hass: The current home assistant instance.
    :param objects: The objects to map.
    :param map_function: Maps the original object to a new object. Note: Throwing an exception or returning None from this function results in the original object being retried later.
    :param async_add_entities: The same function provided to a platform's async_setup_entry function.
    :param retry_interval: Time between attempts to map and process objects.
    :param timeout_attempts: Number of attempts before giving up. A value of 0 means it runs forever.
    :param run_in_parallel: When True, objects will be handled in parallel. (Default: True)
    :return: A function that can be used to cancel future object processing.
    """

    async def async_process_entity(hass: HomeAssistant, entity: Entity) -> None:
        await async_add_entities([entity], update_before_add=update_before_add)

    return await async_map_retry(
        hass,
        objects,
        map_function,
        async_process_entity,
        retry_interval,
        timeout_attempts,
        run_in_parallel,
    )


async def async_map_retry(
    hass: HomeAssistant,
    objects: ObjectsType,
    map_function: MapFunctionType,
    process_function: ProcessFunctionType,
    retry_interval: timedelta = DEFAULT_RETRY_INTERVAL,
    timeout_attempts: int = DEFAULT_TIMEOUT_ATTEMPTS,
    run_in_parallel: bool = DEFAULT_RUN_IN_PARALLEL,
) -> CancelFunctionType:
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
    cancel_func1 = None

    @callback
    def cancel() -> None:
        nonlocal cancel_func1
        cancel_func1()

    async def map_object(original_object: OriginalObjectType) -> MapObjectResult:
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
    async def map_objects(*args) -> None:
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
        # Process object serially.
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
