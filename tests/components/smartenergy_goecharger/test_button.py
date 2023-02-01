"""Test go-e Charger Cloud button inputs."""

from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.smartenergy_goecharger.const import (
    CHARGER_FORCE_CHARGING,
    DOMAIN,
    OFFLINE,
    STATUS,
    TRANSACTION,
    WALLBOX_CONTROL,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant

API_STATUS_RESPONSE = {
    "car_status": "Car is charging",
    "charger_max_current": 2,
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
    **{"charger_force_charging": "on"},
)


API_STATUS_RESPONSE_3 = dict(
    API_STATUS_RESPONSE,
    **{"transaction": 0},
)


API_STATUS_RESPONSE_4 = dict(
    API_STATUS_RESPONSE,
    **{"charger_force_charging": "neutral"},
)


async def test_button_wallbox_charge_stop(
    hass: HomeAssistant, mock_init_component, charger_1
) -> None:
    """Test if pressing the button stops the charging."""
    charger_name = charger_1[CONF_NAME]
    coordinator_name = f"{charger_name}_coordinator"

    # device is in the force state "neutral"
    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_FORCE_CHARGING]
        == "neutral"
    )

    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value=API_STATUS_RESPONSE,
    ), patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.set_force_charging",
        return_value=True,
    ):
        # change the force state to "off"
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            service_data={
                ATTR_ENTITY_ID: f"{BUTTON_DOMAIN}.{DOMAIN}_{charger_name}_{WALLBOX_CONTROL}"
            },
            blocking=True,
        )

    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_FORCE_CHARGING]
        == "off"
    )


async def test_button_wallbox_auth(
    hass: HomeAssistant, mock_init_component, charger_1
) -> None:
    """Test if pressing the button enables the device authentication."""
    charger_name = charger_1[CONF_NAME]
    coordinator_name = f"{charger_name}_coordinator"

    # device has no transaction by default
    assert hass.data[DOMAIN][coordinator_name].data[charger_name][TRANSACTION] is None

    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value=API_STATUS_RESPONSE_3,
    ), patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.set_force_charging",
        return_value=True,
    ):
        # change the transaction to "0" to do the authentication
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            service_data={
                ATTR_ENTITY_ID: f"{BUTTON_DOMAIN}.{DOMAIN}_{charger_name}_{WALLBOX_CONTROL}"
            },
            blocking=True,
        )
    assert hass.data[DOMAIN][coordinator_name].data[charger_name][TRANSACTION] == 0


async def test_button_wallbox_charge_start(
    hass: HomeAssistant, mock_init_component, charger_1
) -> None:
    """Test if pressing the button starts the charging."""
    charger_name = charger_1[CONF_NAME]
    coordinator_name = f"{charger_name}_coordinator"

    # device is in the force state "neutral"
    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_FORCE_CHARGING]
        == "neutral"
    )

    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value=API_STATUS_RESPONSE_2,
    ), patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.set_force_charging",
        return_value=True,
    ):
        # change the force state to "on"
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            service_data={
                ATTR_ENTITY_ID: f"{BUTTON_DOMAIN}.{DOMAIN}_{charger_name}_{WALLBOX_CONTROL}"
            },
            blocking=True,
        )
    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_FORCE_CHARGING]
        == "on"
    )


async def test_button_wallbox_disabled(
    hass: HomeAssistant, mock_init_component, charger_1
) -> None:
    """Test if pressing of the button is disabled when car is not connected."""
    charger_name = charger_1[CONF_NAME]
    coordinator_name = f"{charger_name}_coordinator"

    # device is in the force state "neutral" and trx "None"
    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_FORCE_CHARGING]
        == "neutral"
    )
    assert hass.data[DOMAIN][coordinator_name].data[charger_name][TRANSACTION] is None

    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value=API_STATUS_RESPONSE_4,
    ), patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.set_force_charging",
        return_value=True,
    ):
        # button should be disabled
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            service_data={
                ATTR_ENTITY_ID: f"{BUTTON_DOMAIN}.{DOMAIN}_{charger_name}_{WALLBOX_CONTROL}"
            },
            blocking=True,
        )

    # therefore expect the same values
    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_FORCE_CHARGING]
        == "neutral"
    )
    assert hass.data[DOMAIN][coordinator_name].data[charger_name][TRANSACTION] is None


async def test_button_wallbox_offline(
    hass: HomeAssistant, mock_init_component_offline, charger_1
) -> None:
    """Test if wallbox is set to the offline mode when wallbox itself is offline."""
    charger_name = charger_1[CONF_NAME]
    coordinator_name = f"{charger_name}_coordinator"

    # device should be in the "offline" mode if wallbox is offline
    assert hass.data[DOMAIN][coordinator_name].data[charger_name][STATUS] == OFFLINE


async def test_button_wallbox_charge_stop_config_entry(
    hass: HomeAssistant, mock_init_component_config_flow
) -> None:
    """Test if pressing the button stops the charging (config entry)."""
    charger_name = "test"
    coordinator_name = f"{charger_name}_coordinator"

    # device is in the force state "neutral"
    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_FORCE_CHARGING]
        == "neutral"
    )

    with patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.request_status",
        return_value=API_STATUS_RESPONSE,
    ), patch(
        f"homeassistant.components.{DOMAIN}.state.GoeChargerApi.set_force_charging",
        return_value=True,
    ):
        # change the force state to "off"
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            service_data={
                ATTR_ENTITY_ID: f"{BUTTON_DOMAIN}.{DOMAIN}_{charger_name}_{WALLBOX_CONTROL}"
            },
            blocking=True,
        )

    assert (
        hass.data[DOMAIN][coordinator_name].data[charger_name][CHARGER_FORCE_CHARGING]
        == "off"
    )
