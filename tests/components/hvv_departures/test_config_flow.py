"""Test the HVV Departures config flow."""
import json

from pygti.exceptions import CannotConnect, InvalidAuth

from homeassistant import data_entry_flow
from homeassistant.components.hvv_departures.const import (
    CONF_FILTER,
    CONF_REAL_TIME,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_OFFSET, CONF_PASSWORD, CONF_USERNAME

from tests.async_mock import patch
from tests.common import MockConfigEntry, load_fixture

FIXTURE_INIT = json.loads(load_fixture("hvv_departures/init.json"))
FIXTURE_CHECK_NAME = json.loads(load_fixture("hvv_departures/check_name.json"))
FIXTURE_STATION_INFORMATION = json.loads(
    load_fixture("hvv_departures/station_information.json")
)
FIXTURE_CONFIG_ENTRY = json.loads(load_fixture("hvv_departures/config_entry.json"))
FIXTURE_OPTIONS = json.loads(load_fixture("hvv_departures/options.json"))
FIXTURE_DEPARTURE_LIST = json.loads(load_fixture("hvv_departures/departure_list.json"))


async def test_user_flow(hass):
    """Test that config flow works."""

    with patch(
        "homeassistant.components.hvv_departures.hub.GTI.init",
        return_value=FIXTURE_INIT,
    ), patch("pygti.gti.GTI.checkName", return_value=FIXTURE_CHECK_NAME,), patch(
        "pygti.gti.GTI.stationInformation",
        return_value=FIXTURE_STATION_INFORMATION,
    ), patch(
        "homeassistant.components.hvv_departures.async_setup", return_value=True
    ), patch(
        "homeassistant.components.hvv_departures.async_setup_entry",
        return_value=True,
    ):

        # step: user

        result_user = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: "api-test.geofox.de",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

        assert result_user["step_id"] == "station"

        # step: station
        result_station = await hass.config_entries.flow.async_configure(
            result_user["flow_id"],
            {CONF_STATION: "Wartenau"},
        )

        assert result_station["step_id"] == "station_select"

        # step: station_select
        result_station_select = await hass.config_entries.flow.async_configure(
            result_user["flow_id"],
            {CONF_STATION: "Wartenau"},
        )

        assert result_station_select["type"] == "create_entry"
        assert result_station_select["title"] == "Wartenau"
        assert result_station_select["data"] == {
            CONF_HOST: "api-test.geofox.de",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_STATION: {
                "name": "Wartenau",
                "city": "Hamburg",
                "combinedName": "Wartenau",
                "id": "Master:10901",
                "type": "STATION",
                "coordinate": {"x": 10.035515, "y": 53.56478},
                "serviceTypes": ["bus", "u"],
                "hasStationInformation": True,
            },
        }


async def test_user_flow_no_results(hass):
    """Test that config flow works when there are no results."""

    with patch(
        "homeassistant.components.hvv_departures.hub.GTI.init",
        return_value=FIXTURE_INIT,
    ), patch(
        "pygti.gti.GTI.checkName",
        return_value={"returnCode": "OK", "results": []},
    ), patch(
        "homeassistant.components.hvv_departures.async_setup", return_value=True
    ), patch(
        "homeassistant.components.hvv_departures.async_setup_entry",
        return_value=True,
    ):

        # step: user

        result_user = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: "api-test.geofox.de",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

        assert result_user["step_id"] == "station"

        # step: station
        result_station = await hass.config_entries.flow.async_configure(
            result_user["flow_id"],
            {CONF_STATION: "non_existing_station"},
        )

        assert result_station["step_id"] == "station"
        assert result_station["errors"]["base"] == "no_results"


async def test_user_flow_invalid_auth(hass):
    """Test that config flow handles invalid auth."""

    with patch(
        "homeassistant.components.hvv_departures.hub.GTI.init",
        side_effect=InvalidAuth(
            "ERROR_TEXT",
            "Bei der Verarbeitung der Anfrage ist ein technisches Problem aufgetreten.",
            "Authentication failed!",
        ),
    ):

        # step: user
        result_user = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: "api-test.geofox.de",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

        assert result_user["type"] == "form"
        assert result_user["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass):
    """Test that config flow handles connection errors."""

    with patch(
        "homeassistant.components.hvv_departures.hub.GTI.init",
        side_effect=CannotConnect(),
    ):

        # step: user
        result_user = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: "api-test.geofox.de",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

        assert result_user["type"] == "form"
        assert result_user["errors"] == {"base": "cannot_connect"}


async def test_user_flow_station(hass):
    """Test that config flow handles empty data on step station."""

    with patch(
        "homeassistant.components.hvv_departures.hub.GTI.init",
        return_value=True,
    ), patch(
        "pygti.gti.GTI.checkName",
        return_value={"returnCode": "OK", "results": []},
    ):

        # step: user

        result_user = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: "api-test.geofox.de",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

        assert result_user["step_id"] == "station"

        # step: station
        result_station = await hass.config_entries.flow.async_configure(
            result_user["flow_id"],
            None,
        )
        assert result_station["type"] == "form"
        assert result_station["step_id"] == "station"


async def test_user_flow_station_select(hass):
    """Test that config flow handles empty data on step station_select."""

    with patch(
        "homeassistant.components.hvv_departures.hub.GTI.init",
        return_value=True,
    ), patch(
        "pygti.gti.GTI.checkName",
        return_value=FIXTURE_CHECK_NAME,
    ):
        result_user = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: "api-test.geofox.de",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

        result_station = await hass.config_entries.flow.async_configure(
            result_user["flow_id"],
            {CONF_STATION: "Wartenau"},
        )

        # step: station_select
        result_station_select = await hass.config_entries.flow.async_configure(
            result_station["flow_id"],
            None,
        )

        assert result_station_select["type"] == "form"
        assert result_station_select["step_id"] == "station_select"


async def test_options_flow(hass):
    """Test that options flow works."""

    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Wartenau",
        data=FIXTURE_CONFIG_ENTRY,
        source="user",
        connection_class=CONN_CLASS_CLOUD_POLL,
        system_options={"disable_new_entities": False},
        options=FIXTURE_OPTIONS,
        unique_id="1234",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hvv_departures.hub.GTI.init",
        return_value=True,
    ), patch(
        "pygti.gti.GTI.departureList",
        return_value=FIXTURE_DEPARTURE_LIST,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_FILTER: ["0"], CONF_OFFSET: 15, CONF_REAL_TIME: False},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {
            CONF_FILTER: [
                {
                    "serviceID": "HHA-U:U1_HHA-U",
                    "stationIDs": ["Master:10902"],
                    "label": "Fuhlsbüttel Nord / Ochsenzoll / Norderstedt Mitte / Kellinghusenstraße / Ohlsdorf / Garstedt",
                    "serviceName": "U1",
                }
            ],
            CONF_OFFSET: 15,
            CONF_REAL_TIME: False,
        }


async def test_options_flow_invalid_auth(hass):
    """Test that options flow works."""

    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Wartenau",
        data=FIXTURE_CONFIG_ENTRY,
        source="user",
        connection_class=CONN_CLASS_CLOUD_POLL,
        system_options={"disable_new_entities": False},
        options=FIXTURE_OPTIONS,
        unique_id="1234",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hvv_departures.hub.GTI.init",
        side_effect=InvalidAuth(
            "ERROR_TEXT",
            "Bei der Verarbeitung der Anfrage ist ein technisches Problem aufgetreten.",
            "Authentication failed!",
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        assert result["errors"] == {"base": "invalid_auth"}


async def test_options_flow_cannot_connect(hass):
    """Test that options flow works."""

    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Wartenau",
        data=FIXTURE_CONFIG_ENTRY,
        source="user",
        connection_class=CONN_CLASS_CLOUD_POLL,
        system_options={"disable_new_entities": False},
        options=FIXTURE_OPTIONS,
        unique_id="1234",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "pygti.gti.GTI.departureList",
        side_effect=CannotConnect(),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        assert result["errors"] == {"base": "cannot_connect"}
