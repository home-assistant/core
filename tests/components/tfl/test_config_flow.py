"""Test the Transport for London config flow."""
from unittest import mock
from unittest.mock import AsyncMock, Mock, patch
from urllib.error import HTTPError

import pytest

from homeassistant import config_entries
from homeassistant.components.tfl.config_flow import (
    STEP_STOP_POINT_DATA_SCHEMA,
    STEP_USER_DATA_SCHEMA,
    CannotConnect,
    ConfigFlow,
    InvalidAuth,
)
from homeassistant.components.tfl.const import (
    CONF_API_APP_KEY,
    CONF_STOP_POINT,
    CONF_STOP_POINT_ADD_ANOTHER,
    CONF_STOP_POINTS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_flow_user_init(hass: HomeAssistant) -> None:
    """Test the initialization of the form in the first step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    expected = {
        "data_schema": STEP_USER_DATA_SCHEMA,
        "description_placeholders": None,
        "errors": {},
        "flow_id": mock.ANY,
        "handler": "tfl",
        "last_step": None,
        "step_id": "user",
        "type": FlowResultType.FORM,
    }
    assert expected == result


async def test_flow_stops_form_is_shown(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the initialization of the form in the second step of the config flow."""
    user_config_flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert user_config_flow_result["type"] == FlowResultType.FORM
    assert user_config_flow_result["errors"] == {}

    with patch(
        "homeassistant.components.tfl.config_flow.stopPoint.getCategories",
        return_value={},
    ):
        stops_config_flow__init_result = await hass.config_entries.flow.async_configure(
            user_config_flow_result["flow_id"],
            user_input={CONF_API_APP_KEY: "appy_appy_app_key"},
        )
        await hass.async_block_till_done()

    # Validate that the stops form is shown
    expected = {
        "data_schema": STEP_STOP_POINT_DATA_SCHEMA,
        "description_placeholders": None,
        "errors": {},
        "flow_id": mock.ANY,
        "handler": "tfl",
        "last_step": None,
        "step_id": "stop_point",
        "type": FlowResultType.FORM,
    }
    assert expected == stops_config_flow__init_result


@patch("homeassistant.components.tfl.config_flow.stopPoint")
async def test_flow_stops_does_more_stops(m_stopPoint, hass: HomeAssistant) -> None:
    """Test that the stops step allows for more stops to be entered."""

    m_stop_point_api = Mock()
    m_stop_point_api.getStationArrivals = Mock()
    m_stopPoint.return_value = m_stop_point_api

    ConfigFlow.data = {
        CONF_API_APP_KEY: "appy_appy_app_key",
        CONF_STOP_POINTS: [],
    }
    with patch(
        "homeassistant.components.tfl.config_flow.stopPoint.getStationArrivals",
        return_value={},
    ):
        stops_config_flow_init_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "stop_point"}
        )
        await hass.async_block_till_done()

    with patch("homeassistant.components.tfl.async_setup_entry", return_value=True):
        stops_config_flow_again_result = await hass.config_entries.flow.async_configure(
            stops_config_flow_init_result["flow_id"],
            user_input={
                CONF_STOP_POINT: "AAAAAAAA1",
                CONF_STOP_POINT_ADD_ANOTHER: True,
            },
        )

    # Validate that the stops form was returned again
    expected = {
        "data_schema": STEP_STOP_POINT_DATA_SCHEMA,
        "description_placeholders": None,
        "errors": {},
        "flow_id": mock.ANY,
        "handler": "tfl",
        "last_step": None,
        "step_id": "stop_point",
        "type": FlowResultType.FORM,
    }
    assert expected == stops_config_flow_again_result

    with patch("homeassistant.components.tfl.async_setup_entry", return_value=True):
        stops_config_success_result = await hass.config_entries.flow.async_configure(
            stops_config_flow_init_result["flow_id"],
            user_input={
                CONF_STOP_POINT: "AAAAAAAA2",
            },
        )

    # Validate that config entry was created
    expected = {
        "context": {"source": "stop_point"},
        "description": None,
        "description_placeholders": None,
        "flow_id": mock.ANY,
        "options": {},
        "handler": "tfl",
        "title": "Transport for London",
        "data": {
            CONF_API_APP_KEY: "appy_appy_app_key",
            CONF_STOP_POINTS: ["AAAAAAAA1", "AAAAAAAA2"],
        },
        "type": FlowResultType.CREATE_ENTRY,
        "version": 1,
        "result": mock.ANY,
    }

    assert expected == stops_config_success_result


@patch("homeassistant.components.tfl.config_flow.stopPoint")
async def test_flow_stops_creates_config_entry(
    m_stopPoint, hass: HomeAssistant
) -> None:
    """Test the Config Entry is successfully created."""
    m_stop_point_api = Mock()
    m_stop_point_api.getStationArrivals = Mock()
    m_stopPoint.return_value = m_stop_point_api

    ConfigFlow.data = {
        CONF_API_APP_KEY: "appy_appy_app_key",
        CONF_STOP_POINTS: [],
    }
    with patch(
        "homeassistant.components.tfl.config_flow.stopPoint.getStationArrivals",
        return_value={},
    ):
        stops_config_flow_init_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "stop_point"}
        )
        await hass.async_block_till_done()

    with patch("homeassistant.components.tfl.async_setup_entry", return_value=True):
        stops_config_success_result = await hass.config_entries.flow.async_configure(
            stops_config_flow_init_result["flow_id"],
            user_input={CONF_STOP_POINT: "AAAAAAAA1"},
        )

    # Validate that config entry was created
    expected = {
        # "data_schema": STEP_STOP_POINT_DATA_SCHEMA,
        "context": {"source": "stop_point"},
        "description": None,
        "description_placeholders": None,
        "flow_id": mock.ANY,
        "options": {},
        "handler": "tfl",
        "title": "Transport for London",
        "data": {
            CONF_API_APP_KEY: "appy_appy_app_key",
            CONF_STOP_POINTS: ["AAAAAAAA1"],
        },
        "type": FlowResultType.CREATE_ENTRY,
        "version": 1,
        "result": mock.ANY,
    }

    assert expected == stops_config_success_result


@patch("homeassistant.components.tfl.config_flow.stopPoint")
async def test_form_no_stop(m_stopPoint, hass: HomeAssistant) -> None:
    """Test we handle no stops being entered."""
    m_stop_point_api = Mock()
    m_stop_point_api.getStationArrivals = Mock()
    m_stopPoint.return_value = m_stop_point_api

    ConfigFlow.data = {
        CONF_API_APP_KEY: "appy_appy_app_key",
        CONF_STOP_POINTS: [],
    }
    with patch(
        "homeassistant.components.tfl.config_flow.stopPoint.getStationArrivals",
        return_value={},
    ):
        stops_config_flow_init_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "stop_point"}
        )
        await hass.async_block_till_done()

    with patch("homeassistant.components.tfl.async_setup_entry", return_value=True):
        stops_config_error_result = await hass.config_entries.flow.async_configure(
            stops_config_flow_init_result["flow_id"],
        )

    # Validate that config entry was created
    expected = {
        "data_schema": STEP_STOP_POINT_DATA_SCHEMA,
        "description_placeholders": None,
        "flow_id": mock.ANY,
        "handler": "tfl",
        "step_id": "stop_point",
        "type": FlowResultType.FORM,
        "errors": {},
        "last_step": None,
    }

    assert expected == stops_config_error_result


@patch("homeassistant.components.tfl.config_flow.stopPoint")
async def test_invalid_stop_id(m_stopPoint, hass: HomeAssistant) -> None:
    """Test we handle an invalid stop id being entered."""
    m_stop_point_api = Mock()
    m_stop_point_api.getStationArrivals = Mock(
        side_effect=HTTPError("http://test", 404, "Not Found", None, None)
    )
    m_stopPoint.return_value = m_stop_point_api

    ConfigFlow.data = {
        CONF_API_APP_KEY: "appy_appy_app_key",
        CONF_STOP_POINTS: [],
    }
    with patch(
        "homeassistant.components.tfl.config_flow.stopPoint.getStationArrivals",
        return_value={},
    ):
        stops_config_flow_init_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "stop_point"}
        )
        await hass.async_block_till_done()

    with patch("homeassistant.components.tfl.async_setup_entry", return_value=True):
        stops_config_error_result = await hass.config_entries.flow.async_configure(
            stops_config_flow_init_result["flow_id"],
            user_input={CONF_STOP_POINT: "DOES_NOT_EXIST"},
        )

    # Validate that config entry was created
    expected = {
        "data_schema": STEP_STOP_POINT_DATA_SCHEMA,
        "description_placeholders": None,
        "flow_id": mock.ANY,
        "handler": "tfl",
        "step_id": "stop_point",
        "type": FlowResultType.FORM,
        "errors": {"base": "invalid_stop_point"},
        "last_step": None,
    }

    assert expected == stops_config_error_result


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    user_form_init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tfl.config_flow.validate_app_key",
        side_effect=InvalidAuth,
    ):
        user_form_error_result = await hass.config_entries.flow.async_configure(
            user_form_init_result["flow_id"],
            user_input={
                CONF_API_APP_KEY: "appy_appy_app_key",
            },
        )

    assert user_form_error_result["type"] == FlowResultType.FORM
    assert user_form_error_result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    user_form_init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tfl.config_flow.validate_app_key",
        side_effect=CannotConnect,
    ):
        user_form_error_result = await hass.config_entries.flow.async_configure(
            user_form_init_result["flow_id"],
            user_input={CONF_API_APP_KEY: "appy_appy_app_key"},
        )

    assert user_form_error_result["type"] == FlowResultType.FORM
    assert user_form_error_result["errors"] == {"base": "cannot_connect"}


async def test_options_flow_init(hass: HomeAssistant) -> None:
    """Test that the options flow is successfully initialised."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="unique_id",
        data={
            CONF_API_APP_KEY: "appy_appy_app_key",
            CONF_STOP_POINTS: ["AAAAAAAA1"],
        },
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # show initial form
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert {} == result["errors"]
    assert result["data_schema"]({})["app_key"] == "appy_appy_app_key"
    assert ["AAAAAAAA1"] == result["data_schema"].schema["stops"].options


async def test_options_flow_change_app_key(hass: HomeAssistant) -> None:
    """Test that the options flow allows for the app key to be changed."""
    pytest.fail()


async def test_options_flow_change_stops(hass: HomeAssistant) -> None:
    """Test that the options flow allows for the stops to be changed."""
    pytest.fail()
