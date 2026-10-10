"""Tests for the binary sensor module."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, mock_devices_response

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_sensor_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    # Configure the API devices call for device_name
    mock_devices_response(aioclient_mock, device_name)

    # setup platform - only including the named device
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check device registry
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices == snapshot(name="devices")

    # Check entity registry
    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == BINARY_SENSOR_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


@pytest.mark.parametrize(
    ("light_detection", "room_dark", "expected_state"),
    [(1, 1, STATE_ON), (1, 0, STATE_OFF), (0, 1, STATE_OFF)],
)
async def test_dark_room_needs_light_detection(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    light_detection: int,
    room_dark: int,
    expected_state: str,
) -> None:
    """Test the dark room sensor only reports dark while light detection is on."""
    mock_devices_response(
        aioclient_mock,
        "Air Purifier Vital 200S",
        details_override={
            "lightDetectionSwitch": light_detection,
            "environmentLightState": room_dark,
        },
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.air_purifier_vital_200s_dark_room")
    assert state is not None
    assert state.state == expected_state
