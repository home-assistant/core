"""Test the NMBS config flow."""

from copy import deepcopy
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.nmbs.const import (
    CONF_STATION_FROM,
    CONF_STATION_LIVE,
    CONF_STATION_TO,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import mock_api_unavailable, mock_station_response

DUMMY_DATA: dict[str, Any] = {
    "STAT_BRUSSELS_NORTH": "Brussel-Noord/Bruxelles-Nord",
    "STAT_BRUSSELS_CENTRAL": "Brussel-Centraal/Bruxelles-Central",
    "STAT_BRUSSELS_SOUTH": "Brussel-Zuid/Bruxelles-Midi",
}


async def test_step_connection_no_data(hass: HomeAssistant) -> None:
    """Test starting a flow by user which chooses for connection."""
    with patch(
        "pyrail.irail.iRail.get_stations",
        wraps=mock_station_response,
    ):
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}


@pytest.mark.parametrize(
    "user_input",
    [
        {
            CONF_STATION_FROM: deepcopy(DUMMY_DATA["STAT_BRUSSELS_NORTH"]),
            CONF_STATION_TO: deepcopy(DUMMY_DATA["STAT_BRUSSELS_SOUTH"]),
        }
    ],
)
async def test_step_connection_data(
    hass: HomeAssistant, user_input: dict | None
) -> None:
    """Test starting a flow by user which filled in data for connection."""
    with patch(
        "pyrail.irail.iRail.get_stations",
        wraps=mock_station_response,
    ):
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )

        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "user_input",
    [
        {
            CONF_STATION_FROM: deepcopy(DUMMY_DATA["STAT_BRUSSELS_NORTH"]),
            CONF_STATION_LIVE: deepcopy(DUMMY_DATA["STAT_BRUSSELS_CENTRAL"]),
            CONF_STATION_TO: deepcopy(DUMMY_DATA["STAT_BRUSSELS_SOUTH"]),
        },
    ],
)
async def test_step_import_connection(
    hass: HomeAssistant, user_input: dict | None
) -> None:
    """Test starting a flow by user which filled in data for connection."""
    with patch(
        "pyrail.irail.iRail.get_stations",
        wraps=mock_station_response,
    ):
        connection = user_input.copy()
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=connection
        )

        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "user_input",
    [
        {
            CONF_STATION_FROM: deepcopy(DUMMY_DATA["STAT_BRUSSELS_NORTH"]),
            CONF_STATION_LIVE: deepcopy(DUMMY_DATA["STAT_BRUSSELS_CENTRAL"]),
            CONF_STATION_TO: deepcopy(DUMMY_DATA["STAT_BRUSSELS_SOUTH"]),
        },
    ],
)
async def test_unavailable_api(hass: HomeAssistant, user_input: dict | None) -> None:
    """Test starting a flow by user and api is unavailable."""
    with patch(
        "pyrail.irail.iRail.get_stations",
        wraps=mock_api_unavailable,
    ):
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "api_unavailable"
