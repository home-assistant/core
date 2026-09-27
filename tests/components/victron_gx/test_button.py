"""Tests for Victron GX MQTT button entities."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from victron_mqtt import GenericOnOff, Hub as VictronVenusHub, WritableMetric
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_INSTALLATION_ID

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_button_entities_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test for all Victron GX button entities."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Device/Reboot",
        '{"value": 0}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_button_press(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test pressing a Victron GX button triggers the metric write."""
    victron_hub, _mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Device/Reboot",
        '{"value": 0}',
    )
    await finalize_injection(victron_hub, disconnect=False)
    await hass.async_block_till_done()

    button_entity = entity_registry.async_get("button.victron_venus_device_reboot")

    with patch.object(WritableMetric, "set") as set_mock:
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: button_entity.entity_id},
            blocking=True,
        )

        set_mock.assert_called_once_with(GenericOnOff.ON)
