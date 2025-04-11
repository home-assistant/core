"""Test the switchbot fan."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

from homeassistant.components.fan import (
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from . import CIRCULATOR_FAN_SERVICE_INFO, make_advertisement

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_circulator_fan_controlling(
    hass: HomeAssistant, mock_entry_factory: Callable[[str], MockConfigEntry]
) -> None:
    """Test setting up the circulator controlling."""
    inject_bluetooth_service_info(hass, CIRCULATOR_FAN_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="circulator_fan")
    entity_id = "fan.test_name"
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.switchbot.fan.switchbot.SwitchbotFan.get_basic_info",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.switchbot.fan.switchbot.SwitchbotFan.set_preset_mode",
            new=AsyncMock(return_value=True),
        ) as mock_set_preset_mode,
        patch(
            "homeassistant.components.switchbot.fan.switchbot.SwitchbotFan.set_percentage",
            new=AsyncMock(return_value=True),
        ) as mock_set_percentage,
        patch(
            "homeassistant.components.switchbot.fan.switchbot.SwitchbotFan.set_oscillation",
            new=AsyncMock(return_value=True),
        ) as mock_set_oscillation,
        patch(
            "homeassistant.components.switchbot.fan.switchbot.SwitchbotFan.turn_on",
            new=AsyncMock(return_value=True),
        ) as mock_turn_on,
        patch(
            "homeassistant.components.switchbot.fan.switchbot.SwitchbotFan.turn_off",
            new=AsyncMock(return_value=True),
        ) as mock_turn_off,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "fan.test_name"
        address = "AA:BB:CC:DD:EE:FF"
        service_data = b"~\x00R"

        # Test set preset mode
        manufacturer_data = b"\xb0\xe9\xfeXY\xa8\xfd\xccWO"
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: "BABY"},
            blocking=True,
        )

        inject_bluetooth_service_info(
            hass, make_advertisement(address, manufacturer_data, service_data)
        )
        await hass.async_block_till_done()

        mock_set_preset_mode.assert_awaited_once()
        state = hass.states.get(entity_id)
        assert state.state == STATE_ON
        assert state.attributes[ATTR_PRESET_MODE] == "BABY"

        # Test set percentage
        manufacturer_data = b"\xb0\xe9\xfeXY\xa8\x02\x9cW\x1b"
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 27},
            blocking=True,
        )

        inject_bluetooth_service_info(
            hass, make_advertisement(address, manufacturer_data, service_data)
        )
        await hass.async_block_till_done()

        mock_set_percentage.assert_awaited_once()
        state = hass.states.get(entity_id)
        assert state.state == STATE_ON
        assert state.attributes[ATTR_PERCENTAGE] == 27

        # Test set oscillate
        manufacturer_data = b"\xb0\xe9\xfeXY\xa8\x04\x9eU\x1b"
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_OSCILLATE,
            {ATTR_ENTITY_ID: entity_id, ATTR_OSCILLATING: True},
            blocking=True,
        )

        inject_bluetooth_service_info(
            hass, make_advertisement(address, manufacturer_data, service_data)
        )
        await hass.async_block_till_done()

        mock_set_oscillation.assert_awaited_once()
        state = hass.states.get(entity_id)
        assert state.state == STATE_ON
        assert state.attributes[ATTR_OSCILLATING] is True

        # Test turn off
        manufacturer_data = b"\xb0\xe9\xfeXY\xa8\x06\x1eO\x1b"
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        inject_bluetooth_service_info(
            hass, make_advertisement(address, manufacturer_data, service_data)
        )
        await hass.async_block_till_done()

        mock_turn_off.assert_awaited_once()
        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

        # Test turn on
        manufacturer_data = b"\xb0\xe9\xfeXY\xa8\x07\x9eO\x1b"
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        inject_bluetooth_service_info(
            hass, make_advertisement(address, manufacturer_data, service_data)
        )
        await hass.async_block_till_done()

        mock_turn_on.assert_awaited_once()
        state = hass.states.get(entity_id)
        assert state.state == STATE_ON
