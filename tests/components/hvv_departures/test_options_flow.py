"""Test the HVV Departures config flow."""
from asynctest import patch
from pygti.exceptions import CannotConnect, InvalidAuth

from homeassistant.components.hvv_departures import config_flow
from homeassistant.components.hvv_departures.const import DOMAIN
from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigEntry

from .patched_data import (
    PATCHED_CONFIG_ENTRY_DATA,
    PATCHED_CONFIG_ENTRY_OPTIONS,
    PATCHED_DEPARTURE_LIST,
)


async def test_options_flow(hass):
    """Test that options flow works."""

    config_entry = ConfigEntry(
        1,
        DOMAIN,
        "Wartenau",
        PATCHED_CONFIG_ENTRY_DATA,
        "user",
        CONN_CLASS_CLOUD_POLL,
        {"disable_new_entities": False},
        PATCHED_CONFIG_ENTRY_OPTIONS,
        None,
        "0b74eba16972834dec1a92135fc62676",
    )

    flow = config_flow.OptionsFlowHandler(config_entry)
    flow.hass = hass

    with patch(
        "homeassistant.components.hvv_departures.config_flow.GTIHub.authenticate",
        return_value=True,
    ), patch(
        "pygti.gti.GTI.departureList", return_value=PATCHED_DEPARTURE_LIST,
    ):

        # step: init

        result_init = await flow.async_step_init(
            user_input={
                "filter": "U1, Fuhlsbüttel Nord / Ochsenzoll / Norderstedt Mitte / Kellinghusenstraße / Ohlsdorf / Garstedt",
                "offset": 15,
                "realtime": False,
            }
        )

        assert result_init["type"] == "create_entry"
        assert result_init["data"] == {
            "filter": [
                {
                    "serviceID": "HHA-U:U1_HHA-U",
                    "stationIDs": ["Master:10902"],
                    "label": "Fuhlsbüttel Nord / Ochsenzoll / Norderstedt Mitte / Kellinghusenstraße / Ohlsdorf / Garstedt",
                    "serviceName": "U1",
                }
            ],
            "offset": 15,
            "realtime": False,
        }


async def test_options_flow_options_not_set(hass):
    """Test that options flow works."""

    config_entry = ConfigEntry(
        1,
        DOMAIN,
        "Wartenau",
        PATCHED_CONFIG_ENTRY_DATA,
        "user",
        CONN_CLASS_CLOUD_POLL,
        {"disable_new_entities": False},
        {},
        None,
        "0b74eba16972834dec1a92135fc62676",
    )

    flow = config_flow.OptionsFlowHandler(config_entry)
    flow.hass = hass

    with patch(
        "homeassistant.components.hvv_departures.config_flow.GTIHub.authenticate",
        return_value=True,
    ), patch(
        "pygti.gti.GTI.departureList", return_value=PATCHED_DEPARTURE_LIST,
    ):

        # step: init

        result_init = await flow.async_step_init(user_input=None)

        assert result_init["type"] == "form"


async def test_options_flow_invalid_auth(hass):
    """Test that options flow works."""

    config_entry = ConfigEntry(
        1,
        DOMAIN,
        "Wartenau",
        PATCHED_CONFIG_ENTRY_DATA,
        "user",
        CONN_CLASS_CLOUD_POLL,
        {"disable_new_entities": False},
        PATCHED_CONFIG_ENTRY_OPTIONS,
        None,
        "0b74eba16972834dec1a92135fc62676",
    )

    flow = config_flow.OptionsFlowHandler(config_entry)
    flow.hass = hass

    with patch(
        "homeassistant.components.hvv_departures.config_flow.GTIHub.authenticate",
        side_effect=InvalidAuth(
            "ERROR_TEXT",
            "Bei der Verarbeitung der Anfrage ist ein technisches Problem aufgetreten.",
            "Authentication failed!",
        ),
    ):

        # step: init

        result_init = await flow.async_step_init(
            user_input={
                "filter": "U1, Fuhlsbüttel Nord / Ochsenzoll / Norderstedt Mitte / Kellinghusenstraße / Ohlsdorf / Garstedt",
                "offset": 15,
                "realtime": False,
            }
        )

        assert result_init["type"] == "form"
        assert result_init["errors"] == {"base": "invalid_auth"}


async def test_options_flow_cannot_connect(hass):
    """Test that options flow works."""

    config_entry = ConfigEntry(
        1,
        DOMAIN,
        "Wartenau",
        PATCHED_CONFIG_ENTRY_DATA,
        "user",
        CONN_CLASS_CLOUD_POLL,
        {"disable_new_entities": False},
        PATCHED_CONFIG_ENTRY_OPTIONS,
        None,
        "0b74eba16972834dec1a92135fc62676",
    )

    flow = config_flow.OptionsFlowHandler(config_entry)
    flow.hass = hass

    with patch(
        "pygti.gti.GTI.departureList", side_effect=CannotConnect(),
    ):

        # step: init

        result_init = await flow.async_step_init(
            user_input={
                "filter": "U1, Fuhlsbüttel Nord / Ochsenzoll / Norderstedt Mitte / Kellinghusenstraße / Ohlsdorf / Garstedt",
                "offset": 15,
                "realtime": False,
            }
        )

        assert result_init["type"] == "form"
        assert result_init["errors"] == {"base": "cannot_connect"}


async def test_get_options_flow(hass):
    """Test that the config flow can return an options flow."""

    config_entry = ConfigEntry(
        1,
        DOMAIN,
        "Wartenau",
        PATCHED_CONFIG_ENTRY_DATA,
        "user",
        CONN_CLASS_CLOUD_POLL,
        {"disable_new_entities": False},
        PATCHED_CONFIG_ENTRY_OPTIONS,
        None,
        "0b74eba16972834dec1a92135fc62676",
    )

    flow = config_flow.ConfigFlow()
    flow.hass = hass

    flow_handler = flow.async_get_options_flow(config_entry)

    assert flow_handler.config_entry == config_entry
