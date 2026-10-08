"""Tests for the Abode switch device."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.abode.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

from tests.common import snapshot_platform

AUTOMATION_ID = "switch.test_automation"
DEVICE_ID = "switch.test_switch"


async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all entities."""
    config_entry = await setup_platform(hass, SWITCH_DOMAIN)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_switch_on(hass: HomeAssistant) -> None:
    """Test the switch can be turned on."""
    await setup_platform(hass, SWITCH_DOMAIN)

    with patch("jaraco.abode.devices.switch.Switch.switch_on") as mock_switch_on:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
        )
        await hass.async_block_till_done()

        mock_switch_on.assert_called_once()


async def test_switch_off(hass: HomeAssistant) -> None:
    """Test the switch can be turned off."""
    await setup_platform(hass, SWITCH_DOMAIN)

    with patch("jaraco.abode.devices.switch.Switch.switch_off") as mock_switch_off:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
        )
        await hass.async_block_till_done()

        mock_switch_off.assert_called_once()


async def test_turn_automation_off(hass: HomeAssistant) -> None:
    """Test the automation can be turned off."""
    with patch("jaraco.abode.automation.Automation.enable") as mock_trigger:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: AUTOMATION_ID},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_trigger.assert_called_once_with(False)


async def test_turn_automation_on(hass: HomeAssistant) -> None:
    """Test the automation can be turned on."""
    with patch("jaraco.abode.automation.Automation.enable") as mock_trigger:
        await setup_platform(hass, SWITCH_DOMAIN)

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: AUTOMATION_ID},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_trigger.assert_called_once_with(True)


async def test_trigger_automation(hass: HomeAssistant) -> None:
    """Test the trigger automation service."""
    await setup_platform(hass, SWITCH_DOMAIN)

    with patch("jaraco.abode.automation.Automation.trigger") as mock:
        await hass.services.async_call(
            DOMAIN,
            "trigger_automation",
            {ATTR_ENTITY_ID: AUTOMATION_ID},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock.assert_called_once()


async def test_entity_id_tracking_after_removal(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a removed switch is no longer tracked in the Abode entity ids."""
    config_entry = await setup_platform(hass, SWITCH_DOMAIN)
    assert DEVICE_ID in config_entry.runtime_data.entity_ids

    entity_registry.async_remove(DEVICE_ID)
    await hass.async_block_till_done()

    assert DEVICE_ID not in config_entry.runtime_data.entity_ids


async def test_entity_id_tracking_after_entity_id_change(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a renamed switch is tracked by its new entity id only."""
    config_entry = await setup_platform(hass, SWITCH_DOMAIN)

    # Changing the entity_id removes and re-adds the same entity object.
    entity_registry.async_update_entity(DEVICE_ID, new_entity_id="switch.renamed")
    await hass.async_block_till_done()

    assert DEVICE_ID not in config_entry.runtime_data.entity_ids
    assert "switch.renamed" in config_entry.runtime_data.entity_ids
