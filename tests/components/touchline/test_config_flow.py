"""Test the Touchline config flow."""

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytouchline_extended import RoomStatus, TouchlineConnectionError

from homeassistant import config_entries
from homeassistant.components.touchline.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import ROOM_STATUS, TEST_HOST, TEST_UNIQUE_ID, make_state

TEST_DATA = {CONF_HOST: TEST_HOST}


async def test_form_success(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOST
    assert result["data"] == TEST_DATA
    assert result["result"].unique_id == TEST_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (TouchlineConnectionError, "cannot_connect"),
        (Exception("Unexpected backend explosion"), "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    side_effect: Exception,
    error_key: str,
) -> None:
    """Test errors during input validation are handled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    mock_touchline_controller.fetch_async.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    # "Fix" the problem, and try again.
    mock_touchline_controller.fetch_async.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOST
    assert result["data"] == TEST_DATA
    assert result["result"].unique_id == TEST_UNIQUE_ID


@pytest.mark.parametrize(
    "rooms",
    [
        pytest.param((replace(ROOM_STATUS, controller_id=None),), id="missing-id"),
        pytest.param((), id="no-thermostats"),
    ],
)
async def test_form_missing_controller_id(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    rooms: tuple[RoomStatus, ...],
) -> None:
    """Test a controller without a usable ID is reported as a connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_touchline_controller.fetch_async.return_value = make_state(*rooms)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_touchline_controller.fetch_async.return_value = make_state(ROOM_STATUS)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_UNIQUE_ID


async def test_already_configured_by_host(
    hass: HomeAssistant, mock_touchline_controller: MagicMock
) -> None:
    """Test abort when host is already configured."""
    MockConfigEntry(domain=DOMAIN, data=TEST_DATA).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_already_configured_by_unique_id(
    hass: HomeAssistant, mock_touchline_controller: MagicMock
) -> None:
    """Test abort when unique id is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "5.6.7.8"},
        unique_id=TEST_UNIQUE_ID,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
