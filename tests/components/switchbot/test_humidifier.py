"""Test the switchbot humidifiers."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    ATTR_MODE,
    DOMAIN as HUMIDIFIER_DOMAIN,
    MODE_AUTO,
    MODE_NORMAL,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import HUMIDIFIER_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    (
        "service",
        "service_data",
        "mock_method",
        "expected_args",
    ),
    [
        (
            SERVICE_TURN_OFF,
            {},
            "turn_off",
            (),
        ),
        (
            SERVICE_TURN_ON,
            {},
            "turn_on",
            (),
        ),
        (
            SERVICE_SET_HUMIDITY,
            {ATTR_HUMIDITY: 50},
            "set_humidity_level",
            (50,),
        ),
        (
            SERVICE_SET_MODE,
            {ATTR_MODE: MODE_AUTO},
            "set_auto_mode",
            (),
        ),
        (
            SERVICE_SET_MODE,
            {ATTR_MODE: MODE_NORMAL},
            "set_manual_mode",
            (),
        ),
    ],
)
async def test_humidifier_services(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
    expected_args: tuple,
) -> None:
    """Test all humidifier services with proper parameters."""
    inject_bluetooth_service_info(hass, HUMIDIFIER_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="humidifier")
    entry.add_to_hass(hass)
    entity_id = "humidifier.test_name"

    with (
        patch(
            "homeassistant.components.switchbot.humidifier.switchbot.SwitchbotHumidifier.set_level",
            new=AsyncMock(return_value=True),
        ) as mock_set_humidity_level,
        patch(
            "homeassistant.components.switchbot.humidifier.switchbot.SwitchbotHumidifier.async_set_auto",
            new=AsyncMock(return_value=True),
        ) as mock_set_auto_mode,
        patch(
            "homeassistant.components.switchbot.humidifier.switchbot.SwitchbotHumidifier.async_set_manual",
            new=AsyncMock(return_value=True),
        ) as mock_set_manual_mode,
        patch(
            "homeassistant.components.switchbot.humidifier.switchbot.SwitchbotHumidifier.turn_off",
            new=AsyncMock(return_value=True),
        ) as mock_turn_off,
        patch(
            "homeassistant.components.switchbot.humidifier.switchbot.SwitchbotHumidifier.turn_on",
            new=AsyncMock(return_value=True),
        ) as mock_turn_on,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            service,
            {**service_data, ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mock_map = {
            "turn_off": mock_turn_off,
            "turn_on": mock_turn_on,
            "set_humidity_level": mock_set_humidity_level,
            "set_auto_mode": mock_set_auto_mode,
            "set_manual_mode": mock_set_manual_mode,
        }
        mock_instance = mock_map[mock_method]
        mock_instance.assert_awaited_once_with(*expected_args)
