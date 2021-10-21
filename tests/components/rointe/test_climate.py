"""Tests for the Rointe coordinator."""

from copy import deepcopy
import sys
from unittest.mock import MagicMock, patch

import pytest
from rointesdk.model import RointeProduct
from rointesdk.rointe_api import ApiResponse

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.rointe.const import RointeOperationMode, RointePreset
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant

from .common import (
    MOCK_GET_DEVICE_RESPONSES,
    MOCK_GET_DEVICES_RESPONSE,
    async_init_integration,
)


def get_initial_device_data_mock():
    """Prepare a mock for the API handler."""
    instance_mock = MagicMock()

    # Initialize auth.
    instance_mock.initialize_authentication.return_value = ApiResponse(True, None, None)

    # Firmware map:
    product_map = {
        RointeProduct.RADIATOR_V2: {
            "1_2_5": "2_0_2",
            "1_2_6": "2_0_2",
            "2_0_0": "2_0_2",
            "2_0_1": "2_0_2",
        }
    }

    instance_mock.get_latest_firmware.return_value = ApiResponse(
        True, product_map, None
    )

    # Get all devices.
    instance_mock.get_installation_devices.return_value = MOCK_GET_DEVICES_RESPONSE

    # Device data
    instance_mock.get_device.side_effect = MOCK_GET_DEVICE_RESPONSES.get

    # Get Energy data.
    instance_mock.get_latest_energy_stats.return_value = ApiResponse(False, None, None)

    return instance_mock


async def test_climate_set_hvac_mode_heat(hass: HomeAssistant) -> None:
    """Tests setting HVAC mode to manual."""
    with patch.object(
        sys.modules["homeassistant.components.rointe"], "RointeAPI"
    ) as mock_rointe_api:
        instance_mock = get_initial_device_data_mock()
        mock_rointe_api.return_value = instance_mock

        # State changing methods.
        instance_mock.set_device_mode.return_value = ApiResponse(True, None, None)

        # Begin test.
        await async_init_integration(hass)

        # setup new data for the update call that will happen after the temperature is changed.
        new_device_data = deepcopy(MOCK_GET_DEVICE_RESPONSES["device-2"].data)
        new_device_data["data"]["temp"] = 17
        new_device_data["data"]["mode"] = RointeOperationMode.MANUAL.value
        new_device_data["data"]["power"] = True

        instance_mock.get_device.side_effect = {
            "device-1": MOCK_GET_DEVICE_RESPONSES["device-1"],
            "device-2": ApiResponse(True, new_device_data, None),
        }.get

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.office", ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )

        instance_mock.set_device_mode.assert_called_once()
        call_args = instance_mock.set_device_mode.call_args_list[0][0]

        assert call_args[0].id == "device-2"
        assert call_args[1] == HVACMode.HEAT

        assert hass.states.get("climate.office").attributes.get(ATTR_TEMPERATURE) == 17
        assert (
            hass.states.get("climate.office").attributes.get(ATTR_PRESET_MODE) is None
        )
        assert (
            hass.states.get("climate.office").attributes.get(ATTR_HVAC_ACTION)
            == HVACAction.HEATING
        )


async def test_climate_entity_set_temp(hass: HomeAssistant) -> None:
    """Test setting the radiator temperature."""
    with patch.object(
        sys.modules["homeassistant.components.rointe"], "RointeAPI"
    ) as mock_rointe_api:
        instance_mock = get_initial_device_data_mock()
        mock_rointe_api.return_value = instance_mock

        # State changing methods.
        instance_mock.set_device_temp.return_value = ApiResponse(True, None, None)

        # Begin test.
        await async_init_integration(hass)

        # setup new data for the update call that will happen after the temperature is changed.
        new_device_data = deepcopy(MOCK_GET_DEVICE_RESPONSES["device-2"].data)
        new_device_data["data"]["temp"] = 28
        new_device_data["data"]["mode"] = RointeOperationMode.MANUAL.value
        new_device_data["data"]["power"] = True

        instance_mock.get_device.side_effect = {
            "device-1": MOCK_GET_DEVICE_RESPONSES["device-1"],
            "device-2": ApiResponse(True, new_device_data, None),
        }.get

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.office",
                ATTR_TEMPERATURE: 28.0,
            },
            blocking=True,
        )

        assert hass.states.get("climate.office").attributes.get(ATTR_TEMPERATURE) == 28
        assert (
            hass.states.get("climate.office").attributes.get(ATTR_PRESET_MODE) is None
        )
        assert (
            hass.states.get("climate.office").attributes.get(ATTR_HVAC_ACTION)
            == HVACAction.HEATING
        )

        # Attempt setting an invalid temperature
        with pytest.raises(ValueError):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                {
                    ATTR_ENTITY_ID: "climate.office",
                    ATTR_TEMPERATURE: -10,
                },
                blocking=True,
            )


async def test_climate_set_preset_eco(hass: HomeAssistant) -> None:
    """Tests setting the preset to ECO."""
    with patch.object(
        sys.modules["homeassistant.components.rointe"], "RointeAPI"
    ) as mock_rointe_api:
        instance_mock = get_initial_device_data_mock()
        mock_rointe_api.return_value = instance_mock

        # State changing methods.
        instance_mock.set_device_preset.return_value = ApiResponse(True, None, None)

        # Begin test.
        await async_init_integration(hass)

        # setup new data for the update call that will happen after the temperature is changed.
        new_device_data = deepcopy(MOCK_GET_DEVICE_RESPONSES["device-2"].data)
        new_device_data["data"]["power"] = True
        new_device_data["data"]["temp"] = new_device_data["data"]["eco"]
        new_device_data["data"]["mode"] = RointeOperationMode.MANUAL.value
        new_device_data["data"]["status"] = RointePreset.ECO

        instance_mock.get_device.side_effect = {
            "device-1": MOCK_GET_DEVICE_RESPONSES["device-1"],
            "device-2": ApiResponse(True, new_device_data, None),
        }.get

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: "climate.office", ATTR_PRESET_MODE: RointePreset.ECO},
            blocking=True,
        )

        instance_mock.set_device_preset.assert_called_once()
        call_args = instance_mock.set_device_preset.call_args_list[0][0]

        assert call_args[0].id == "device-2"
        assert call_args[1] == RointePreset.ECO

        assert (
            hass.states.get("climate.office").attributes.get(ATTR_TEMPERATURE)
            == new_device_data["data"]["eco"]
        )
        assert (
            hass.states.get("climate.office").attributes.get(ATTR_PRESET_MODE)
            == RointePreset.ECO
        )
        assert (
            hass.states.get("climate.office").attributes.get(ATTR_HVAC_ACTION)
            == HVACAction.HEATING
        )
