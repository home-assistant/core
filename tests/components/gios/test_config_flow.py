"""Define tests for the GIOS config flow."""
from asynctest import patch

from homeassistant import data_entry_flow
from homeassistant.components.gios import config_flow
from homeassistant.components.gios.const import CONF_STATION_ID, DOMAIN
from homeassistant.const import CONF_NAME

from tests.common import MockConfigEntry

CONFIG = {
    CONF_NAME: "Foo",
    CONF_STATION_ID: 123,
}

VALID_STATIONS = [
    {"id": 123, "stationName": "Test Name 1", "gegrLat": "99.99", "gegrLon": "88.88"},
    {"id": 321, "stationName": "Test Name 2", "gegrLat": "77.77", "gegrLon": "66.66"},
]

VALID_STATION = [
    {"id": 3764, "param": {"paramName": "particulate matter PM10", "paramCode": "PM10"}}
]

VALID_INDEXES = {
    "stIndexLevel": {"id": 1, "indexLevelName": "Good"},
    "pm10IndexLevel": {"id": 0, "indexLevelName": "Very good"},
}

VALID_SENSOR = {"key": "PM10", "values": [{"value": 11.11}]}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.GiosFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_invalid_station_id(hass):
    """Test that errors are shown when measuring station ID is invalid."""
    with patch("gios.Gios._get_stations", return_value=VALID_STATIONS):
        flow = config_flow.GiosFlowHandler()
        flow.hass = hass

        result = await flow.async_step_user(
            user_input={CONF_NAME: "Foo", CONF_STATION_ID: 0}
        )

        assert result["errors"] == {CONF_STATION_ID: "wrong_station_id"}


async def test_duplicate_name_error(hass):
    """Test that errors are shown when duplicate names are added."""
    with patch("gios.Gios._get_stations", return_value=VALID_STATIONS), patch(
        "gios.Gios._get_station", return_value=VALID_STATION
    ), patch("gios.Gios._get_station", return_value=VALID_STATION), patch(
        "gios.Gios._get_sensor", return_value=VALID_SENSOR
    ), patch(
        "gios.Gios._get_indexes", return_value=VALID_INDEXES
    ):
        MockConfigEntry(domain=DOMAIN, data=CONFIG).add_to_hass(hass)
        flow = config_flow.GiosFlowHandler()
        flow.hass = hass

        result = await flow.async_step_user(
            user_input={CONF_NAME: "Foo", CONF_STATION_ID: 321}
        )

        assert result["errors"] == {CONF_NAME: "name_exists"}


async def test_duplicate_station_id_error(hass):
    """Test that errors are shown when duplicate stations IDs are added."""
    with patch("gios.Gios._get_stations", return_value=VALID_STATIONS), patch(
        "gios.Gios._get_station", return_value=VALID_STATION
    ), patch("gios.Gios._get_station", return_value=VALID_STATION), patch(
        "gios.Gios._get_sensor", return_value=VALID_SENSOR
    ), patch(
        "gios.Gios._get_indexes", return_value=VALID_INDEXES
    ):
        MockConfigEntry(domain=DOMAIN, data=CONFIG).add_to_hass(hass)
        flow = config_flow.GiosFlowHandler()
        flow.hass = hass

        result = await flow.async_step_user(
            user_input={CONF_NAME: "Other", CONF_STATION_ID: 123}
        )

        assert result["errors"] == {CONF_STATION_ID: "station_id_exists"}


async def test_invalid_sensor_data(hass):
    """Test that errors are shown when sensor data is invalid."""
    with patch("gios.Gios._get_stations", return_value=VALID_STATIONS), patch(
        "gios.Gios._get_station", return_value=VALID_STATION
    ), patch("gios.Gios._get_station", return_value=VALID_STATION), patch(
        "gios.Gios._get_sensor", return_value={}
    ):
        flow = config_flow.GiosFlowHandler()
        flow.hass = hass

        result = await flow.async_step_user(user_input=CONFIG)

        assert result["errors"] == {CONF_STATION_ID: "invalid_sensors_data"}


async def test_create_entry(hass):
    """Test that the user step works."""
    with patch("gios.Gios._get_stations", return_value=VALID_STATIONS), patch(
        "gios.Gios._get_station", return_value=VALID_STATION
    ), patch("gios.Gios._get_station", return_value=VALID_STATION), patch(
        "gios.Gios._get_sensor", return_value=VALID_SENSOR
    ), patch(
        "gios.Gios._get_indexes", return_value=VALID_INDEXES
    ):
        flow = config_flow.GiosFlowHandler()
        flow.hass = hass

        result = await flow.async_step_user(user_input=CONFIG)

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == CONFIG[CONF_NAME]
        assert result["data"][CONF_STATION_ID] == CONFIG[CONF_STATION_ID]
