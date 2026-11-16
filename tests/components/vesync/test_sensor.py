"""Tests for the sensor module."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, ENTITY_HUMIDIFIER_HUMIDITY, mock_devices_response


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
        if entity.domain == SENSOR_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


@pytest.mark.parametrize(
    ("cook_status", "expected_state"),
    [
        pytest.param(None, "unknown", id="missing"),
        pytest.param("appointing", "appointing", id="appointing"),
    ],
)
async def test_cook_status(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    cook_status: str | None,
    expected_state: str,
) -> None:
    """Test cook status values supported by the integration."""
    mock_devices_response(
        aioclient_mock,
        "CS158-AF Air Fryer Cooking",
        details_override={"cookStatus": cook_status},
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.cs158_af_air_fryer_cooking_cooking_status")
    assert state is not None
    assert state.state == expected_state


async def test_humidity(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test the state of humidity sensor entity."""

    assert hass.states.get(ENTITY_HUMIDIFIER_HUMIDITY).state == "35"
