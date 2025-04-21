"""Define tests for the GIOS config flow."""

import json
from unittest.mock import patch

from gios import ApiError

from homeassistant.components.gios import config_flow
from homeassistant.components.gios.const import CONF_STATION_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import STATIONS

from tests.common import load_fixture

CONFIG = {
    CONF_NAME: "Foo",
    CONF_STATION_ID: "123",
}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    with patch(
        "homeassistant.components.gios.coordinator.Gios._get_stations",
        return_value=STATIONS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_form_with_api_error(hass: HomeAssistant) -> None:
    """Test the form is aborted because of API error."""
    with patch(
        "homeassistant.components.gios.coordinator.Gios._get_stations",
        side_effect=ApiError("error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT


async def test_invalid_sensor_data(hass: HomeAssistant) -> None:
    """Test that errors are shown when sensor data is invalid."""
    with (
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_stations",
            return_value=STATIONS,
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_station",
            return_value=json.loads(load_fixture("gios/station.json")),
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_sensor",
            return_value={},
        ),
    ):
        flow = config_flow.GiosFlowHandler()
        flow.hass = hass
        flow.context = {}

        result = await flow.async_step_user(user_input=CONFIG)

        assert result["errors"] == {CONF_STATION_ID: "invalid_sensors_data"}


async def test_cannot_connect(hass: HomeAssistant) -> None:
    """Test that errors are shown when cannot connect to GIOS server."""
    with (
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_stations",
            return_value=STATIONS,
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._async_get",
            side_effect=ApiError("error"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )
        await hass.async_block_till_done()

    assert result["errors"] == {"base": "cannot_connect"}


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    with (
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_stations",
            return_value=STATIONS,
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_station",
            return_value=json.loads(load_fixture("gios/station.json")),
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_all_sensors",
            return_value=json.loads(load_fixture("gios/sensors.json")),
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_indexes",
            return_value=json.loads(load_fixture("gios/indexes.json")),
        ),
    ):
        flow = config_flow.GiosFlowHandler()
        flow.hass = hass
        flow.context = {}

        result = await flow.async_step_user(user_input=CONFIG)

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Test Name 1"
        assert result["data"][CONF_STATION_ID] == CONFIG[CONF_STATION_ID]

        assert flow.context["unique_id"] == "123"
