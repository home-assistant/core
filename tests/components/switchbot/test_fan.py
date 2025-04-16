"""Test the switchbot fan."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest

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


@pytest.mark.parametrize(
    (
        "service",
        "service_data",
        "mock_method",
        "expected_attributes",
        "expected_state",
        "manufacturer_data",
    ),
    [
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "BABY"},
            "set_preset_mode",
            {ATTR_PRESET_MODE: "BABY"},
            STATE_ON,
            b"\xb0\xe9\xfeXY\xa8\xfd\xccWO",
        ),
        (
            SERVICE_SET_PERCENTAGE,
            {ATTR_PERCENTAGE: 27},
            "set_percentage",
            {ATTR_PERCENTAGE: 27},
            STATE_ON,
            b"\xb0\xe9\xfeXY\xa8\x02\x9cW\x1b",
        ),
        (
            SERVICE_OSCILLATE,
            {ATTR_OSCILLATING: True},
            "set_oscillation",
            {ATTR_OSCILLATING: True},
            STATE_ON,
            b"\xb0\xe9\xfeXY\xa8\x04\x9eU\x1b",
        ),
        (
            SERVICE_TURN_OFF,
            {},
            "turn_off",
            {},
            STATE_OFF,
            b"\xb0\xe9\xfeXY\xa8\x06\x1eO\x1b",
        ),
        (
            SERVICE_TURN_ON,
            {},
            "turn_on",
            {},
            STATE_ON,
            b"\xb0\xe9\xfeXY\xa8\x07\x9eO\x1b",
        ),
    ],
)
async def test_circulator_fan_controlling(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
    expected_attributes: dict,
    expected_state: str,
    manufacturer_data: bytes,
) -> None:
    """Test controlling the circulator fan with different services."""
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

        data = {ATTR_ENTITY_ID: entity_id}
        data.update(service_data)

        await hass.services.async_call(
            FAN_DOMAIN,
            service,
            data,
            blocking=True,
        )

        address = "AA:BB:CC:DD:EE:FF"
        adv_service_data = b"~\x00R"
        inject_bluetooth_service_info(
            hass,
            make_advertisement(address, manufacturer_data, adv_service_data),
        )
        await hass.async_block_till_done()

        mock_mapping = {
            "set_preset_mode": mock_set_preset_mode,
            "set_percentage": mock_set_percentage,
            "set_oscillation": mock_set_oscillation,
            "turn_on": mock_turn_on,
            "turn_off": mock_turn_off,
        }
        mock_instance = mock_mapping[mock_method]
        mock_instance.assert_awaited_once()

        state = hass.states.get(entity_id)
        assert state.state == expected_state
        for attr, value in expected_attributes.items():
            assert state.attributes.get(attr) == value
