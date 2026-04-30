"""Tests for Victron GX MQTT button entities."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

from victron_mqtt import Hub as VictronVenusHub
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.victron_gx.const import DOMAIN
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import MOCK_INSTALLATION_ID

from tests.common import MockConfigEntry


async def test_victron_button(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test BUTTON MetricKind - platform reboot button is created."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Device/Reboot",
        '{"value": 0}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entities) == 1
    entity = entities[0]
    assert entity.entity_id == "button.victron_venus_device_reboot"
    assert entity.unique_id == f"{MOCK_INSTALLATION_ID}_system_0_platform_device_reboot"
    assert entity.translation_key == "platform_device_reboot"
    assert entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entity.entity_category is EntityCategory.DIAGNOSTIC

    # Entity is disabled by default, so state is not available
    state = hass.states.get(entity.entity_id)
    assert state is None

    # Verify device info was registered correctly
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_INSTALLATION_ID}_system_0")}
    )
    assert device is not None
    assert device.manufacturer == "Victron Energy"


async def test_victron_button_press(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test button _on_update_cb and pressing it via service call."""
    victron_hub, mock_config_entry = init_integration

    # Enable the button entity before injecting so it gets a state
    entity_registry.async_get_or_create(
        "button",
        DOMAIN,
        f"{MOCK_INSTALLATION_ID}_system_0_platform_device_reboot",
        config_entry=mock_config_entry,
        disabled_by=None,
    )

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Device/Reboot",
        '{"value": 0}',
    )
    await finalize_injection(victron_hub, disconnect=False)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    button_entities = [e for e in entities if e.domain == "button"]
    assert len(button_entities) == 1
    entity_id = button_entities[0].entity_id

    # Inject an update to exercise _on_update_cb (the pass branch)
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Device/Reboot",
        '{"value": 1}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    assert victron_hub._client is not None
    publish_mock = cast(MagicMock, victron_hub._client.publish)
    publish_mock.reset_mock()

    # Call the press service to cover async_press()
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )

    publish_mock.assert_called_once_with(
        f"W/{MOCK_INSTALLATION_ID}/platform/0/Device/Reboot",
        '{"value": 1}',
    )
