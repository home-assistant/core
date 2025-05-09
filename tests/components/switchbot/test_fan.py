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
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from . import CIRCULATOR_FAN_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    (
        "service",
        "service_data",
        "mock_method",
    ),
    [
        (
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "baby"},
            "set_preset_mode",
        ),
        (
            SERVICE_SET_PERCENTAGE,
            {ATTR_PERCENTAGE: 27},
            "set_percentage",
        ),
        (
            SERVICE_OSCILLATE,
            {ATTR_OSCILLATING: True},
            "set_oscillation",
        ),
        (
            SERVICE_TURN_OFF,
            {},
            "turn_off",
        ),
        (
            SERVICE_TURN_ON,
            {},
            "turn_on",
        ),
    ],
)
async def test_circulator_fan_controlling(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
) -> None:
    """Test controlling the circulator fan with different services."""
    inject_bluetooth_service_info(hass, CIRCULATOR_FAN_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="circulator_fan")
    entity_id = "fan.test_name"
    entry.add_to_hass(hass)

    mocked_instance = AsyncMock(return_value=True)
    mcoked_none_instance = AsyncMock(return_value=None)
    with patch.multiple(
        "homeassistant.components.switchbot.fan.switchbot.SwitchbotFan",
        get_basic_info=mcoked_none_instance,
        **{mock_method: mocked_instance},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            FAN_DOMAIN,
            service,
            {**service_data, ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mocked_instance.assert_awaited_once()
