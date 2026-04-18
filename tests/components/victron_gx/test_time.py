"""Tests for Victron GX MQTT time entities."""

from __future__ import annotations

from datetime import time as dt_time

from victron_mqtt import Hub as VictronVenusHub
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.victron_gx.const import DOMAIN
from homeassistant.components.victron_gx.time import VictronTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import MOCK_INSTALLATION_ID

from tests.common import MockConfigEntry


async def test_victron_time(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test TIME MetricKind - ESS schedule charge start time is created and updated."""
    victron_hub, mock_config_entry = init_integration

    # 480 raw seconds, library converts to 8 minutes -> time(0, 8)
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/settings/0/Settings/CGwacs/BatteryLife/Schedule/Charge/0/Start",
        '{"value": 480}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entities) == 1
    entity = entities[0]
    assert (
        entity.entity_id == "time.victron_venus_ess_batterylife_schedule_charge_0_start"
    )
    assert (
        entity.unique_id
        == f"{MOCK_INSTALLATION_ID}_system_0_system_ess_schedule_charge_0_start"
    )
    assert entity.translation_key == "system_ess_schedule_charge_slot_start"

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "00:08:00"

    # Verify device info was registered correctly
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_INSTALLATION_ID}_system_0")}
    )
    assert device is not None
    assert device.manufacturer == "Victron Energy"

    # Update: 3600 raw seconds, library converts to 60 minutes -> time(1, 0)
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/settings/0/Settings/CGwacs/BatteryLife/Schedule/Charge/0/Start",
        '{"value": 3600}',
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "01:00:00"


def test_victron_time_to_time_none() -> None:
    """Test that victron_time_to_time returns None when given None."""
    assert VictronTime.victron_time_to_time(None) is None


async def test_victron_time_actions(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test time None handling and the set_value service call."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/settings/0/Settings/CGwacs/BatteryLife/Schedule/Charge/0/Start",
        '{"value": 480}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 1
    entity_id = entities[0].entity_id

    # Inject null to cover the None branch in victron_time_to_time
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/settings/0/Settings/CGwacs/BatteryLife/Schedule/Charge/0/Start",
        '{"value": null}',
    )
    await hass.async_block_till_done()

    # Call set_value service to cover async_set_value() and time_to_victron_time()
    await hass.services.async_call(
        "time",
        "set_value",
        {"entity_id": entity_id, "time": dt_time(9, 0)},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "09:00:00"
