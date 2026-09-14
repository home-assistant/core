"""Tests for the Switchbot climate integration."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest
from switchbot import SwitchbotOperationError

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import SMART_THERMOSTAT_RADIATOR_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    ("service", "service_data", "mock_method"),
    [
        (SERVICE_SET_HVAC_MODE, {"hvac_mode": HVACMode.HEAT}, "set_hvac_mode"),
        (SERVICE_SET_PRESET_MODE, {"preset_mode": "manual"}, "set_preset_mode"),
        (SERVICE_SET_TEMPERATURE, {"temperature": 22}, "set_target_temperature"),
    ],
)
async def test_smart_thermostat_radiator_controlling(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
) -> None:
    """Test controlling the smart thermostat radiator with different services."""
    inject_bluetooth_service_info(hass, SMART_THERMOSTAT_RADIATOR_SERVICE_INFO)

    entry = mock_entry_encrypted_factory("smart_thermostat_radiator")
    entity_id = "climate.test_name"
    entry.add_to_hass(hass)

    mocked_instance = AsyncMock(return_value=True)
    mocked_none_instance = AsyncMock(return_value=None)
    with patch.multiple(
        "homeassistant.components.switchbot.climate.switchbot.SwitchbotSmartThermostatRadiator",
        get_basic_info=mocked_none_instance,
        update=mocked_none_instance,
        **{mock_method: mocked_instance},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {**service_data, ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mocked_instance.assert_awaited_once()


@pytest.mark.parametrize(
    ("service", "service_data", "mock_method"),
    [
        (SERVICE_SET_HVAC_MODE, {"hvac_mode": HVACMode.HEAT}, "set_hvac_mode"),
        (SERVICE_SET_PRESET_MODE, {"preset_mode": "manual"}, "set_preset_mode"),
        (SERVICE_SET_TEMPERATURE, {"temperature": 22}, "set_target_temperature"),
    ],
)
@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            SwitchbotOperationError("Operation failed"),
            "An error occurred while performing the action: Operation failed",
        ),
    ],
)
async def test_exception_handling_smart_thermostat_radiator_service(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    service: str,
    service_data: dict,
    mock_method: str,
    exception: Exception,
    error_message: str,
) -> None:
    """Test exception handling for smart thermostat radiator service with exception."""
    inject_bluetooth_service_info(hass, SMART_THERMOSTAT_RADIATOR_SERVICE_INFO)

    entry = mock_entry_encrypted_factory("smart_thermostat_radiator")
    entry.add_to_hass(hass)
    entity_id = "climate.test_name"

    mocked_none_instance = AsyncMock(return_value=None)
    with patch.multiple(
        "homeassistant.components.switchbot.climate.switchbot.SwitchbotSmartThermostatRadiator",
        get_basic_info=mocked_none_instance,
        update=mocked_none_instance,
        **{mock_method: AsyncMock(side_effect=exception)},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match=error_message):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                service,
                {**service_data, ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
