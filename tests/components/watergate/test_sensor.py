"""Tests for the Watergate valve platform."""

from collections.abc import Generator

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .const import DEFAULT_NETWORKING_STATE, DEFAULT_TELEMETRY_STATE, MOCK_WEBHOOK_ID

from tests.common import AsyncMock, MockConfigEntry, patch, snapshot_platform
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states of the sensor."""
    freezer.move_to("2021-01-09 12:00:00+00:00")
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

    assert len(entries) == 5
    for entry in entries:
        assert entry.disabled


async def test_telemetry_webhook(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test if water flow webhook is handled correctly."""
    await init_integration(hass, mock_entry)

    def assert_state(entity_id: str, expected_state: str):
        state = hass.states.get(entity_id)
        assert state.state == str(expected_state)

    assert_state("sensor.sonic_volume_flow_rate", DEFAULT_TELEMETRY_STATE.flow)
    assert_state("sensor.sonic_water_pressure", DEFAULT_TELEMETRY_STATE.pressure)
    assert_state(
        "sensor.sonic_water_temperature", DEFAULT_TELEMETRY_STATE.water_temperature
    )

    telemetry_change_data = {
        "type": "telemetry",
        "data": {"flow": 2137, "pressure": 1910, "temperature": 20},
    }
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{MOCK_WEBHOOK_ID}", json=telemetry_change_data)

    await hass.async_block_till_done()

    assert_state("sensor.sonic_volume_flow_rate", "2.137")
    assert_state("sensor.sonic_water_pressure", "1910")
    assert_state("sensor.sonic_water_temperature", "20")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_wifi_webhook(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test if water flow webhook is handled correctly."""
    await init_integration(hass, mock_entry)

    def assert_state(entity_id: str, expected_state: str):
        state = hass.states.get(entity_id)
        assert state.state == str(expected_state)

    assert_state("sensor.sonic_signal_strength", DEFAULT_NETWORKING_STATE.rssi)

    wifi_change_data = {
        "type": "wifi-changed",
        "data": {
            "ip": "192.168.2.137",
            "gateway": "192.168.2.1",
            "ssid": "Sonic 2",
            "rssi": -70,
            "subnet": "255.255.255.0",
        },
    }
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{MOCK_WEBHOOK_ID}", json=wifi_change_data)

    await hass.async_block_till_done()

    assert_state("sensor.sonic_signal_strength", "-70")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_power_supply_webhook(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
) -> None:
    """Test if water flow webhook is handled correctly."""
    await init_integration(hass, mock_entry)
    entity_id = "sensor.sonic_power_supply_mode"
    registered_entity = hass.states.get(entity_id)
    assert registered_entity
    assert registered_entity.state == "battery"

    power_supply_change_data = {
        "type": "power-supply-changed",
        "data": {"supply": "external"},
    }
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{MOCK_WEBHOOK_ID}", json=power_supply_change_data)

    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "external"
