"""Test ESPHome binary sensors."""

from collections.abc import Awaitable, Callable

from aioesphomeapi import (
    APIClient,
    BinarySensorInfo,
    BinarySensorState,
    EntityInfo,
    EntityState,
    UserService,
)
import pytest

from homeassistant.components.esphome import DomainData
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDevice

from tests.common import MockConfigEntry


async def test_assist_in_progress(
    hass: HomeAssistant,
    mock_voice_assistant_v1_entry,
) -> None:
    """Test assist in progress binary sensor."""

    entry_data = DomainData.get(hass).get_entry_data(mock_voice_assistant_v1_entry)

    state = hass.states.get("binary_sensor.test_assist_in_progress")
    assert state is not None
    assert state.state == "off"

    entry_data.async_set_assist_pipeline_state(True)

    state = hass.states.get("binary_sensor.test_assist_in_progress")
    assert state.state == "on"

    entry_data.async_set_assist_pipeline_state(False)

    state = hass.states.get("binary_sensor.test_assist_in_progress")
    assert state.state == "off"


@pytest.mark.parametrize(
    "binary_state", [(True, STATE_ON), (False, STATE_OFF), (None, STATE_UNKNOWN)]
)
async def test_binary_sensor_generic_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    binary_state: tuple[bool, str],
    mock_generic_device_entry: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockConfigEntry],
    ],
) -> None:
    """Test a generic binary_sensor entity."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
        )
    ]
    esphome_state, hass_state = binary_state
    states = [BinarySensorState(key=1, state=esphome_state)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == hass_state


async def test_status_binary_sensor(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockConfigEntry],
    ],
) -> None:
    """Test a generic binary_sensor entity."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
            is_status_binary_sensor=True,
        )
    ]
    states = [BinarySensorState(key=1, state=None)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON


async def test_binary_sensor_missing_state(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockConfigEntry],
    ],
) -> None:
    """Test a generic binary_sensor that is missing state."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
        )
    ]
    states = [BinarySensorState(key=1, state=True, missing_state=True)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_binary_sensor_has_state_false(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a generic binary_sensor where has_state is false."""
    entity_info = [
        BinarySensorInfo(
            object_id="mybinary_sensor",
            key=1,
            name="my binary_sensor",
            unique_id="my_binary_sensor",
        )
    ]
    states = []
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    mock_device.set_state(BinarySensorState(key=1, state=True, missing_state=False))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_mybinary_sensor")
    assert state is not None
    assert state.state == STATE_ON
