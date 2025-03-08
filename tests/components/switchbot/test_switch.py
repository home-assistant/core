"""Test the switchbot switches."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.switchbot.const import (
    CONF_ENCRYPTION_KEY,
    CONF_KEY_ID,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_SENSOR_TYPE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import WORELAY_SWITCH_1PM_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_relay_switch_1pm_controlling(hass: HomeAssistant) -> None:
    """Test setting up and controlling the relay switch 1pm."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WORELAY_SWITCH_1PM_SERVICE_INFO)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "relay_switch_1pm",
            CONF_KEY_ID: "ff",
            CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        },
        unique_id="aabbccddeeaa",
    )
    entry.add_to_hass(hass)
    with (
        patch("switchbot.SwitchbotRelaySwitch.update", return_value=True),
        patch(
            "switchbot.SwitchbotRelaySwitch.turn_on", new=AsyncMock(return_value=True)
        ) as mock_turn_on,
        patch(
            "switchbot.SwitchbotRelaySwitch.turn_off", new=AsyncMock(return_value=True)
        ) as mock_turn_off,
        patch("switchbot.SwitchbotRelaySwitch.is_on", new=Mock()) as mock_is_on,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "switch.test_name"
        assert hass.states.get(entity_id).state == STATE_ON

        # Test turn off
        mock_is_on.return_value = False
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_turn_off.assert_awaited_once()
        assert hass.states.get(entity_id).state == STATE_OFF

        # Test turn on
        mock_is_on.return_value = True
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_turn_on.assert_awaited_once()
        assert hass.states.get(entity_id).state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_mode(hass: HomeAssistant) -> None:
    """Test the device switch mode is false."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WORELAY_SWITCH_1PM_SERVICE_INFO)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "relay_switch_1pm",
            CONF_KEY_ID: "ff",
            CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        },
        unique_id="aabbccddeeaa",
    )
    entry.add_to_hass(hass)

    with (
        patch("switchbot.SwitchbotRelaySwitch.update", return_value=True),
        patch("switchbot.SwitchbotDevice.switch_mode", return_value=False),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "switch.test_name"
        assert hass.states.get(entity_id).state == STATE_OFF
