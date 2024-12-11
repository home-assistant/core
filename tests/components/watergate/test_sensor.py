"""Tests for the Watergate valve platform."""

from collections.abc import Generator

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .const import MOCK_WEBHOOK_ID

from tests.common import AsyncMock, MockConfigEntry, patch, snapshot_platform
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
    snapshot: SnapshotAssertion,
) -> None:
    """Test states of the sensor."""
    with patch("homeassistant.components.watergate.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


async def test_diagnostics_are_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test if all diagnostic entities are disabled by default."""
    with patch("homeassistant.components.watergate.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_entry)

    entries = [
        entry
        for entry in entity_registry.entities.get_entries_for_config_entry_id(
            mock_entry.entry_id
        )
        if entry.entity_category == EntityCategory.DIAGNOSTIC
    ]

    assert len(entries) == 9
    for entry in entries:
        assert entry.disabled


@pytest.mark.parametrize(
    "params",
    [
        {"entity_id": "sensor.sonic_water_flow_rate", "result": "2.137"},
        {"entity_id": "sensor.sonic_water_pressure", "result": "1910"},
        {"entity_id": "sensor.sonic_water_temperature", "result": "20"},
    ],
)
async def test_telemetry_webhook(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_entry: MockConfigEntry,
    params: dict[str, str],
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test if water flow webhook is handled correctly."""
    await init_integration(hass, mock_entry)

    registered_entity = hass.states.get(params["entity_id"])
    assert registered_entity
    assert registered_entity.state == "unknown"

    telemetry_change_data = {
        "type": "telemetry",
        "data": {"flow": 2137, "pressure": 1910, "temperature": 20},
    }
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{MOCK_WEBHOOK_ID}", json=telemetry_change_data)

    await hass.async_block_till_done()

    assert hass.states.get(params["entity_id"]).state == params["result"]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "params",
    [
        {"entity_id": "sensor.sonic_ssid", "result": "Sonic"},
        {"entity_id": "sensor.sonic_rssi", "result": "-50"},
        {"entity_id": "sensor.sonic_subnet", "result": "255.255.255.0"},
        {"entity_id": "sensor.sonic_gateway", "result": "192.168.2.1"},
        {"entity_id": "sensor.sonic_ip", "result": "192.168.2.137"},
    ],
)
async def test_wifi_webhook(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_entry: MockConfigEntry,
    params: dict[str, str],
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test if water flow webhook is handled correctly."""
    await init_integration(hass, mock_entry)

    registered_entity = hass.states.get(params["entity_id"])
    assert registered_entity
    assert registered_entity.state == "unknown"

    wifi_change_data = {
        "type": "wifi-changed",
        "data": {
            "ip": "192.168.2.137",
            "gateway": "192.168.2.1",
            "ssid": "Sonic",
            "rssi": -50,
            "subnet": "255.255.255.0",
        },
    }
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{MOCK_WEBHOOK_ID}", json=wifi_change_data)

    await hass.async_block_till_done()

    assert hass.states.get(params["entity_id"]).state == params["result"]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_power_supply_webhook(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test if water flow webhook is handled correctly."""
    await init_integration(hass, mock_entry)
    entity_id = "sensor.sonic_power_supply"
    registered_entity = hass.states.get(entity_id)
    assert registered_entity
    assert registered_entity.state == "unknown"

    power_supply_change_data = {
        "type": "power-supply-changed",
        "data": {"supply": "external"},
    }
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{MOCK_WEBHOOK_ID}", json=power_supply_change_data)

    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "external"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_aso_report_webhook(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test if water flow webhook is handled correctly."""
    await init_integration(hass, mock_entry)
    entity_id = "sensor.sonic_last_auto_shut_off_event"
    registered_entity = hass.states.get(entity_id)
    assert registered_entity
    assert registered_entity.state == "unknown"

    valve_change_data = {
        "type": "auto-shut-off-report",
        "data": {
            "type": "VOLUME_THRESHOLD",
            "volume": 1000,
            "duration": 60,
            "timestamp": 1630000000,
        },
    }
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{MOCK_WEBHOOK_ID}", json=valve_change_data)

    await hass.async_block_till_done()

    entity_to_check = hass.states.get(entity_id)

    assert entity_to_check.state == "2021-08-26T17:46:40+00:00"
    assert entity_to_check.attributes["volume"] == 1000
    assert entity_to_check.attributes["duration"] == 60
    assert entity_to_check.attributes["type"] == "VOLUME_THRESHOLD"
