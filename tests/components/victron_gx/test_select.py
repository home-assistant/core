"""Tests for Victron GX MQTT select entities."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from victron_mqtt import Hub as VictronVenusHub, WritableMetric
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.victron_gx.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import MOCK_INSTALLATION_ID


async def test_victron_select(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test SELECT MetricKind - EV charger mode select is created and updated."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/evcharger/0/Mode",
        '{"value": 0}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entities) == 1
    entity = entities[0]
    assert entity.entity_id == "select.ev_charging_station_mode"
    assert entity.unique_id == f"{MOCK_INSTALLATION_ID}_evcharger_0_evcharger_mode"

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "manual"
    assert state.attributes["options"] == ["manual", "auto", "scheduled_charge"]

    # Verify device info was registered correctly
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{MOCK_INSTALLATION_ID}_evcharger_0"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Victron Energy"

    # Update the metric to exercise the entity update callback path.
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/evcharger/0/Mode",
        '{"value": 1}',
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == "auto"


async def test_victron_select_actions(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test select_option service calls and library validation errors."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/evcharger/0/Mode",
        '{"value": 0}',
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
    assert state.state == "manual"

    # Call select_option service and verify the entity updates.
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "auto"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "auto"

    error = ValueError("The metric no longer accepts this option")
    with (
        patch.object(WritableMetric, "set", side_effect=error) as set_value,
        pytest.raises(ServiceValidationError) as err,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "manual"},
            blocking=True,
        )

    set_value.assert_called_once_with("manual")
    assert err.value.__cause__ is error
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "invalid_value"
    assert str(err.value) == (
        "The requested value is not valid for this setting on the GX device"
    )


async def test_select_main_topic_has_translation_key(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that select entities with main_topic=True still have translation_key set.

    Regression test: previously main_topic entities skipped setting translation_key,
    breaking HA state/option translations.
    """
    victron_hub, mock_config_entry = init_integration

    # vebus Mode has main_topic=True
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/vebus/289/Mode",
        '{"value": 3}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entities) == 1
    entity = entities[0]
    # translation_key must be set even for main_topic entities
    assert entity.translation_key is not None, (
        "main_topic entity must have translation_key"
    )
    assert entity.translation_key == "vebus_inverter_mode"
    # original_name should be None (uses device name via has_entity_name)
    assert entity.original_name is None
