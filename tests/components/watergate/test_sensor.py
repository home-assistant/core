"""Tests for the Watergate sensor platform."""

from collections.abc import Generator

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    AsyncMock,
    MockConfigEntry,
    patch,
    snapshot_platform,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from watergate_local_api import WatergateApiException

from homeassistant.const import STATE_UNAVAILABLE, EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .const import DEFAULT_NETWORKING_STATE, DEFAULT_TELEMETRY_STATE, MOCK_WEBHOOK_ID


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


@pytest.mark.parametrize(
    ("device_state_v2_side_effect", "negative_volume", "negative_duration"),
    [
        pytest.param(None, "0.3", "25", id="firmware_with_device_state_v2"),
        pytest.param(
            WatergateApiException("Unsupported media type"),
            STATE_UNAVAILABLE,
            STATE_UNAVAILABLE,
            id="firmware_without_device_state_v2",
        ),
    ],
)
async def test_water_meter_sensors(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_watergate_client: Generator[AsyncMock],
    device_state_v2_side_effect: WatergateApiException | None,
    negative_volume: str,
    negative_duration: str,
) -> None:
    """Test the water meter sensors on firmware with and without device state v2."""
    mock_watergate_client.async_get_device_state_v2.side_effect = (
        device_state_v2_side_effect
    )

    with patch("homeassistant.components.watergate.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_entry)

    def assert_state(entity_id: str, expected_state: str) -> None:
        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_state

    # Firmware without v2 reports a single differential meter, surfaced as the positive one.
    assert_state("sensor.sonic_water_meter_volume", "1.2")
    assert_state("sensor.sonic_water_meter_duration", "100")
    assert_state("sensor.sonic_water_meter_negative_volume", negative_volume)
    assert_state("sensor.sonic_water_meter_negative_duration", negative_duration)


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
        "data": {"supply": "external_battery"},
    }
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{MOCK_WEBHOOK_ID}", json=power_supply_change_data)

    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "battery_external"
