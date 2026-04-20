"""Tests for Victron GX MQTT number entities."""

from __future__ import annotations

from victron_mqtt import Hub as VictronVenusHub
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.victron_gx.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import MOCK_INSTALLATION_ID

from tests.common import MockConfigEntry


async def test_victron_number_with_step(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test NUMBER entity with a metric that has a numeric step value."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/settings/0/Settings/SystemSetup/MaxChargeVoltage",
        '{"value": 57.6}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 1
    entity = entities[0]
    assert entity.entity_id == "number.victron_venus_ess_max_charge_voltage"
    assert (
        entity.unique_id
        == f"{MOCK_INSTALLATION_ID}_system_0_system_ess_max_charge_voltage"
    )
    assert entity.original_device_class is NumberDeviceClass.VOLTAGE
    assert entity.unit_of_measurement == "V"
    assert entity.translation_key == "system_ess_max_charge_voltage"

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "57.6"
    assert state.attributes["device_class"] == "voltage"
    assert state.attributes["unit_of_measurement"] == "V"
    assert state.attributes["step"] == 0.1
    assert state.attributes["min"] == 0.0
    assert state.attributes["max"] == 100.0

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_INSTALLATION_ID}_system_0")}
    )
    assert device is not None
    assert device.manufacturer == "Victron Energy"


async def test_victron_number_update(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test number entity updates its value when a new MQTT message arrives."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/settings/0/Settings/SystemSetup/MaxChargeVoltage",
        '{"value": 57.6}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 1
    entity_id = entities[0].entity_id

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "57.6"

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/settings/0/Settings/SystemSetup/MaxChargeVoltage",
        '{"value": 58.0}',
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "58.0"


async def test_victron_number_actions(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test set_value service call."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/evcharger/0/SetCurrent",
        '{"value": 12}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 1
    entity_id = entities[0].entity_id

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "12"

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 20.0},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "20"
