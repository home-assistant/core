"""Tests for the Tibber binary sensors."""

from __future__ import annotations

from unittest.mock import AsyncMock

import tibber

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


def create_tibber_device_with_binary_sensors(
    device_id: str = "device-id",
    external_id: str = "external-id",
    name: str = "Test Device",
    brand: str = "Tibber",
    model: str = "Gen1",
    connector_status: str | None = "connected",
    charging_status: str | None = "charging",
    device_status: str | None = "on",
    home_id: str = "home-id",
) -> tibber.data_api.TibberDevice:
    """Create a fake Tibber Data API device with binary sensor capabilities."""
    device_data = {
        "id": device_id,
        "externalId": external_id,
        "info": {
            "name": name,
            "brand": brand,
            "model": model,
        },
        "capabilities": [
            {
                "id": "connector.status",
                "value": connector_status,
                "description": "Connector status",
                "unit": "",
            },
            {
                "id": "charging.status",
                "value": charging_status,
                "description": "Charging status",
                "unit": "",
            },
            {
                "id": "onOff",
                "value": device_status,
                "description": "Device status",
                "unit": "",
            },
        ],
    }
    return tibber.data_api.TibberDevice(device_data, home_id=home_id)


async def test_binary_sensors_are_created(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: AsyncMock,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
) -> None:
    """Ensure binary sensors are created from Data API devices."""
    device = create_tibber_device_with_binary_sensors()
    data_api_client_mock.get_all_devices = AsyncMock(return_value={"device-id": device})
    data_api_client_mock.update_devices = AsyncMock(return_value={"device-id": device})

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    connector_unique_id = "external-id_connector.status"
    connector_entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, connector_unique_id
    )
    assert connector_entity_id is not None
    state = hass.states.get(connector_entity_id)
    assert state is not None
    assert state.state == "on"

    charging_unique_id = "external-id_charging.status"
    charging_entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, charging_unique_id
    )
    assert charging_entity_id is not None
    state = hass.states.get(charging_entity_id)
    assert state is not None
    assert state.state == "on"

    device_unique_id = "external-id_onOff"
    device_entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, device_unique_id
    )
    assert device_entity_id is not None
    state = hass.states.get(device_entity_id)
    assert state is not None
    assert state.state == "on"


async def test_device_status_on(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: AsyncMock,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device status on state."""
    device = create_tibber_device_with_binary_sensors(device_status="on")
    data_api_client_mock.get_all_devices = AsyncMock(return_value={"device-id": device})
    data_api_client_mock.update_devices = AsyncMock(return_value={"device-id": device})

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    unique_id = "external-id_onOff"
    entity_id = entity_registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


async def test_device_status_off(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: AsyncMock,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test device status off state."""
    device = create_tibber_device_with_binary_sensors(device_status="off")
    data_api_client_mock.get_all_devices = AsyncMock(return_value={"device-id": device})
    data_api_client_mock.update_devices = AsyncMock(return_value={"device-id": device})

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    unique_id = "external-id_onOff"
    entity_id = entity_registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"
