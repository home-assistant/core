"""Test go-e Charger Cloud select inputs."""

from unittest.mock import patch

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.smartenergy_goecharger.const import (
    DOMAIN,
    PHASE_SWITCH_MODE,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.helpers.typing import HomeAssistantType

API_STATUS_RESPONSE = {
    "car_status": "Car is charging",
    "charger_max_current": 2,
    "charging_allowed": "on",
    "energy_since_car_connected": None,
    "energy_total": None,
    "phase_switch_mode": 2,
    "phases_number_connected": 1,
    "charger_access": False,
    "charger_force_charging": "off",
    "min_charging_current_limit": 1,
    "max_charging_current_limit": 30,
    "transaction": None,
}


async def test_select_input_set_phase(
    hass: HomeAssistantType, mock_init_component, charger_1
) -> None:
    """Test if setting of the set phase select input works."""
    charger_name = charger_1[CONF_NAME]
    coordinator_name = f"{charger_name}_coordinator"

    # default value is 1
    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][PHASE_SWITCH_MODE] == 1
    )

    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value=API_STATUS_RESPONSE,
    ), patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.set_phase",
        return_value=True,
    ):
        # change and expected value is 2
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            service_data={
                ATTR_ENTITY_ID: f"{SELECT_DOMAIN}.{DOMAIN}_{charger_name}_{PHASE_SWITCH_MODE}",
                ATTR_OPTION: 2,
            },
            blocking=True,
        )

    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][PHASE_SWITCH_MODE] == 2
    )


async def test_select_input_set_phase_config_entry(
    hass: HomeAssistantType, mock_init_component_config_flow
) -> None:
    """Test if setting of the set phase select input works (config entry)."""
    charger_name = "test"
    coordinator_name = f"{charger_name}_coordinator"

    # default value is 1
    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][PHASE_SWITCH_MODE] == 1
    )

    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value=API_STATUS_RESPONSE,
    ), patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.set_phase",
        return_value=True,
    ):
        # change and expected value is 2
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            service_data={
                ATTR_ENTITY_ID: f"{SELECT_DOMAIN}.{DOMAIN}_{charger_name}_{PHASE_SWITCH_MODE}",
                ATTR_OPTION: 2,
            },
            blocking=True,
        )

    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][PHASE_SWITCH_MODE] == 2
    )
