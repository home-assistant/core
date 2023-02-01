"""Test go-e Charger Cloud number inputs."""

from unittest.mock import patch

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.smartenergy_goecharger.const import (
    CHARGER_MAX_CURRENT,
    DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.helpers.typing import HomeAssistantType

API_STATUS_RESPONSE = {
    "car_status": "Car is charging",
    "charger_max_current": 4,
    "charging_allowed": "on",
    "energy_since_car_connected": None,
    "energy_total": None,
    "phase_switch_mode": 1,
    "phases_number_connected": 1,
    "charger_access": False,
    "charger_force_charging": "off",
    "min_charging_current_limit": 1,
    "max_charging_current_limit": 30,
    "transaction": None,
}

API_STATUS_RESPONSE_2 = dict(
    API_STATUS_RESPONSE,
    **{"charger_max_current": 2},
)


async def test_number_input_max_current_change(
    hass: HomeAssistantType, mock_init_component, charger_1
) -> None:
    """Test if changing of the max current number input works."""
    charger_name = charger_1[CONF_NAME]
    coordinator_name = f"{charger_name}_coordinator"

    # default value is 2
    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_MAX_CURRENT] == 2
    )

    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value=API_STATUS_RESPONSE,
    ), patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.set_max_current",
        return_value=True,
    ):
        # change and expected value is 4
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            service_data={
                ATTR_ENTITY_ID: f"{NUMBER_DOMAIN}.{DOMAIN}_{charger_name}_{CHARGER_MAX_CURRENT}",
                ATTR_VALUE: 4,
            },
            blocking=True,
        )

    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_MAX_CURRENT] == 4
    )


async def test_number_input_max_current_change_wrong_limits(
    hass: HomeAssistantType, mock_init_component_limits, charger_1
) -> None:
    """Test if changing of the max current number doesn't work if limits are set incorrectly."""
    charger_name = charger_1[CONF_NAME]
    coordinator_name = f"{charger_name}_coordinator"

    # default value is 2
    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_MAX_CURRENT] == 2
    )
    # number input shouldn't even be created
    assert (
        f"{NUMBER_DOMAIN}.{DOMAIN}_{charger_name}_{CHARGER_MAX_CURRENT}"
        not in hass.states.async_entity_ids()
    )

    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value=API_STATUS_RESPONSE_2,
    ), patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.set_max_current",
        return_value=True,
    ):
        # therefore, change this change/call shouldn't do anything
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            service_data={
                ATTR_ENTITY_ID: f"{NUMBER_DOMAIN}.{DOMAIN}_{charger_name}_{CHARGER_MAX_CURRENT}",
                ATTR_VALUE: 4,
            },
            blocking=True,
        )

    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_MAX_CURRENT] == 2
    )


async def test_number_input_max_current_change_config_entry(
    hass: HomeAssistantType, mock_init_component_config_flow
) -> None:
    """Test if changing of the max current number input works (config entry)."""
    charger_name = "test"
    coordinator_name = f"{charger_name}_coordinator"

    # default value is 2
    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_MAX_CURRENT] == 2
    )

    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value=API_STATUS_RESPONSE,
    ), patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.set_max_current",
        return_value=True,
    ):
        # change and expected value is 4
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            service_data={
                ATTR_ENTITY_ID: f"{NUMBER_DOMAIN}.{DOMAIN}_{charger_name}_{CHARGER_MAX_CURRENT}",
                ATTR_VALUE: 4,
            },
            blocking=True,
        )

    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_MAX_CURRENT] == 4
    )
