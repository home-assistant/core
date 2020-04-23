"""Test Home Assistant processor util methods."""
from datetime import timedelta

from asynctest import CoroutineMock
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util
from homeassistant.util.processor import async_add_entities_retry, async_map_retry

from tests.common import async_fire_time_changed


class SimpleEntity(Entity):
    """Simple entity for testing."""

    def __init__(self, name: str):
        """Initialize the object."""
        self._name = name

    @property
    def name(self) -> str:
        """Get the name of the entity."""
        return self._name


ORIGINAL_OBJECTS = (
    "object0",
    "object1",
    "object2",
    "object3",
)

NEW_OBJECTS = (
    SimpleEntity(ORIGINAL_OBJECTS[0]),
    SimpleEntity(ORIGINAL_OBJECTS[1]),
    SimpleEntity(ORIGINAL_OBJECTS[2]),
    SimpleEntity(ORIGINAL_OBJECTS[3]),
)

MAP_FUNCTION_SIDE_EFFECTS = (
    # Attempt 1
    Exception(""),  # object0
    None,  # object1
    None,  # object2
    Exception(""),  # object3
    # Attempt 2
    Exception(""),  # object0
    NEW_OBJECTS[1],  # object1
    Exception(""),  # object2
    NEW_OBJECTS[3],  # object3
    # Attempt 3
    NEW_OBJECTS[0],  # object0
    Exception(""),  # object2
    # Attempt 4
    Exception(""),  # object2
    # Attempt 5
    NEW_OBJECTS[2],  # object2
)


async def test_async_add_entities_retry(hass: HomeAssistant) -> None:
    """Test adding entities with retry map."""

    async def map_function(hass: HomeAssistant, original_object: str) -> Entity:
        return SimpleEntity(original_object)

    async_add_entities = CoroutineMock()

    cancel_function = await async_add_entities_retry(
        hass, ORIGINAL_OBJECTS, map_function, async_add_entities
    )
    assert hasattr(cancel_function, "__call__")
    await hass.async_block_till_done()

    assert len(async_add_entities.await_args_list) == len(ORIGINAL_OBJECTS)
    for index, args in enumerate(async_add_entities.await_args_list):
        assert args
        assert args[0][0]
        assert isinstance(args[0][0], list)
        assert args[0][0][0].name == ORIGINAL_OBJECTS[index]


@pytest.mark.parametrize(["run_in_parallel"], [[True], [False]])
async def test_async_map_retry_map_with_errors(
    hass: HomeAssistant, run_in_parallel: bool
) -> None:
    """Test mapping objects encountering errors in parallel or serial."""
    map_function = CoroutineMock(side_effect=MAP_FUNCTION_SIDE_EFFECTS)

    process_function = CoroutineMock()
    now = dt_util.utcnow()

    # Attempt 1
    await async_map_retry(
        hass,
        ORIGINAL_OBJECTS,
        map_function,
        process_function,
        run_in_parallel=run_in_parallel,
    )
    await hass.async_block_till_done()
    assert map_function.await_count == 4
    for original_object in ORIGINAL_OBJECTS:
        map_function.assert_any_await(hass, original_object)

    # Attempt 2
    map_function.reset_mock()
    process_function.reset_mock()
    async_fire_time_changed(hass, now + timedelta(minutes=6))
    await hass.async_block_till_done()
    assert map_function.await_count == 4
    assert process_function.await_count == 2
    process_function.assert_any_await(hass, NEW_OBJECTS[1])
    process_function.assert_any_await(hass, NEW_OBJECTS[3])

    # Attempt 3
    map_function.reset_mock()
    process_function.reset_mock()
    async_fire_time_changed(hass, now + timedelta(minutes=6))
    await hass.async_block_till_done()
    assert map_function.await_count == 2
    assert process_function.await_count == 1
    process_function.assert_any_await(hass, NEW_OBJECTS[0])

    # Attempt 4
    map_function.reset_mock()
    process_function.reset_mock()
    async_fire_time_changed(hass, now + timedelta(minutes=6))
    await hass.async_block_till_done()
    assert map_function.await_count == 1
    assert process_function.await_count == 0

    # Attempt 5
    map_function.reset_mock()
    process_function.reset_mock()
    async_fire_time_changed(hass, now + timedelta(minutes=6))
    await hass.async_block_till_done()
    assert map_function.await_count == 1
    assert process_function.await_count == 1
    process_function.assert_any_await(hass, NEW_OBJECTS[2])


async def test_async_map_retry_map_with_cancel(hass: HomeAssistant) -> None:
    """Test mapping and cancel it mid way through."""
    map_function = CoroutineMock(side_effect=MAP_FUNCTION_SIDE_EFFECTS)

    process_function = CoroutineMock()
    now = dt_util.utcnow()

    # Attempt 1
    cancel_function = await async_map_retry(
        hass, ORIGINAL_OBJECTS, map_function, process_function
    )
    assert hasattr(cancel_function, "__call__")
    await hass.async_block_till_done()
    assert map_function.await_count == 4
    for original_object in ORIGINAL_OBJECTS:
        map_function.assert_any_await(hass, original_object)

    cancel_function()

    # Attempt 2
    map_function.reset_mock()
    process_function.reset_mock()
    async_fire_time_changed(hass, now + timedelta(minutes=6))
    await hass.async_block_till_done()
    assert map_function.await_count == 0
    assert process_function.await_count == 0

    # Attempt 2
    map_function.reset_mock()
    process_function.reset_mock()
    async_fire_time_changed(hass, now + timedelta(minutes=6))
    await hass.async_block_till_done()
    assert map_function.await_count == 0
    assert process_function.await_count == 0


async def test_async_map_retry_map_with_timeout(hass: HomeAssistant) -> None:
    """Test mapping with a timeout."""
    map_function = CoroutineMock(side_effect=MAP_FUNCTION_SIDE_EFFECTS)

    process_function = CoroutineMock()
    now = dt_util.utcnow()

    # Attempt 1
    cancel_function = await async_map_retry(
        hass, ORIGINAL_OBJECTS, map_function, process_function, timeout_attempts=2
    )
    assert hasattr(cancel_function, "__call__")
    await hass.async_block_till_done()
    assert map_function.await_count == 4
    for original_object in ORIGINAL_OBJECTS:
        map_function.assert_any_await(hass, original_object)

    # Attempt 2
    map_function.reset_mock()
    process_function.reset_mock()
    async_fire_time_changed(hass, now + timedelta(minutes=6))
    await hass.async_block_till_done()
    assert map_function.await_count == 4
    assert process_function.await_count == 2
    process_function.assert_any_await(hass, NEW_OBJECTS[1])
    process_function.assert_any_await(hass, NEW_OBJECTS[3])

    # Attempt 3
    map_function.reset_mock()
    process_function.reset_mock()
    async_fire_time_changed(hass, now + timedelta(minutes=6))
    await hass.async_block_till_done()
    assert map_function.await_count == 0
    assert process_function.await_count == 0

    # Attempt 4
    map_function.reset_mock()
    process_function.reset_mock()
    async_fire_time_changed(hass, now + timedelta(minutes=6))
    await hass.async_block_till_done()
    assert map_function.await_count == 0
    assert process_function.await_count == 0
