"""Define tests for the GIOS config flow."""
import json
from unittest.mock import patch

from gios import ApiError

from homeassistant import data_entry_flow
from homeassistant.components.gios import config_flow
from homeassistant.components.gios.const import CONF_STATION_ID
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from . import STATIONS

from tests.common import load_fixture

CONFIG = {
    CONF_NAME: "Foo",
    CONF_STATION_ID: 123,
}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    flow = config_flow.GiosFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_invalid_station_id(hass: HomeAssistant) -> None:
    """Test that errors are shown when measuring station ID is invalid."""
    with patch(
        "homeassistant.components.gios.Gios._get_stations", return_value=STATIONS
    ):
        flow = config_flow.GiosFlowHandler()
        flow.hass = hass
        flow.context = {}

        result = await flow.async_step_user(
            user_input={CONF_NAME: "Foo", CONF_STATION_ID: 0}
        )

        assert result["errors"] == {CONF_STATION_ID: "wrong_station_id"}


async def test_invalid_sensor_data(hass: HomeAssistant) -> None:
    """Test that errors are shown when sensor data is invalid."""
    with patch(
        "homeassistant.components.gios.Gios._get_stations", return_value=STATIONS
    ), patch(
        "homeassistant.components.gios.Gios._get_station",
        return_value=json.loads(load_fixture("gios/station.json")),
    ), patch(
        "homeassistant.components.gios.Gios._get_sensor",
        return_value={},
    ):
        flow = config_flow.GiosFlowHandler()
        flow.hass = hass
        flow.context = {}

        result = await flow.async_step_user(user_input=CONFIG)

        assert result["errors"] == {CONF_STATION_ID: "invalid_sensors_data"}


async def test_cannot_connect(hass: HomeAssistant) -> None:
    """Test that errors are shown when cannot connect to GIOS server."""
    with patch(
        "homeassistant.components.gios.Gios._async_get", side_effect=ApiError("error")
    ):
        flow = config_flow.GiosFlowHandler()
        flow.hass = hass
        flow.context = {}

        result = await flow.async_step_user(user_input=CONFIG)

        assert result["errors"] == {"base": "cannot_connect"}


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    with patch(
        "homeassistant.components.gios.Gios._get_stations",
        return_value=STATIONS,
    ), patch(
        "homeassistant.components.gios.Gios._get_station",
        return_value=json.loads(load_fixture("gios/station.json")),
    ), patch(
        "homeassistant.components.gios.Gios._get_all_sensors",
        return_value=json.loads(load_fixture("gios/sensors.json")),
    ), patch(
        "homeassistant.components.gios.Gios._get_indexes",
        return_value=json.loads(load_fixture("gios/indexes.json")),
    ):
        flow = config_flow.GiosFlowHandler()
        flow.hass = hass
        flow.context = {}

        result = await flow.async_step_user(user_input=CONFIG)

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "Test Name 1"
        assert result["data"][CONF_STATION_ID] == CONFIG[CONF_STATION_ID]

        assert flow.context["unique_id"] == "123"
