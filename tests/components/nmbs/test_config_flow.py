"""Test the NMBS config flow."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.nmbs.config_flow import CONF_EXCLUDE_VIAS
from homeassistant.components.nmbs.const import (
    CONF_STATION_FROM,
    CONF_STATION_LIVE,
    CONF_STATION_TO,
    DOMAIN,
)
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from tests.common import MockConfigEntry

from . import mock_api_unavailable, mock_station_response

DUMMY_DATA: dict[str, Any] = {
    "STAT_BRUSSELS_NORTH": "Brussel-Noord/Bruxelles-Nord",
    "STAT_BRUSSELS_CENTRAL": "Brussel-Centraal/Bruxelles-Central",
    "STAT_BRUSSELS_SOUTH": "Brussel-Zuid/Bruxelles-Midi",
}


@pytest.mark.parametrize(
    "user_input",
    [
        {
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        }
    ],
)
async def test_step_connection_data(
    hass: HomeAssistant, user_input: dict | None
) -> None:
    """Test starting a flow by user which filled in data for connection."""
    with patch(
        "homeassistant.components.nmbs.iRail.get_stations",
        wraps=mock_station_response,
    ):
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert (
            result["title"]
            == "Train from Brussel-Noord/Bruxelles-Nord to Brussel-Zuid/Bruxelles-Midi"
        )
        assert result["data"] == {
            CONF_STATION_FROM: "Brussel-Noord/Bruxelles-Nord",
            CONF_STATION_TO: "Brussel-Zuid/Bruxelles-Midi",
        }


@pytest.mark.parametrize(
    "user_input",
    [
        {
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        }
    ],
)
async def test_step_connection_abort_if_already_setup(
    hass: HomeAssistant, user_input: dict | None
) -> None:
    """Test starting a flow by user which filled in data for connection for already existing connection."""
    MockConfigEntry(
        domain=DOMAIN,
        data=user_input,
        unique_id=f"{user_input[CONF_STATION_FROM]}-{user_input[CONF_STATION_TO]}",
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.nmbs.iRail.get_stations",
        wraps=mock_station_response,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=user_input,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "user_input",
    [
        {
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_LIVE: DUMMY_DATA["STAT_BRUSSELS_CENTRAL"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        },
    ],
)
async def test_unavailable_api(hass: HomeAssistant, user_input: dict | None) -> None:
    """Test starting a flow by user and api is unavailable."""
    with patch(
        "homeassistant.components.nmbs.iRail.get_stations",
        wraps=mock_api_unavailable,
    ):
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "api_unavailable"


# tests around the import flow from configuration.yaml to config entries
@pytest.mark.parametrize(
    "user_input",
    [
        {
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_LIVE: DUMMY_DATA["STAT_BRUSSELS_CENTRAL"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        },
    ],
)
async def test_step_import_connection(
    hass: HomeAssistant, user_input: dict | None
) -> None:
    """Test starting a flow by user which filled in data for connection."""
    with patch(
        "homeassistant.components.nmbs.iRail.get_stations",
        wraps=mock_station_response,
    ):
        connection = user_input.copy()
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=connection
        )

        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert (
            result["title"]
            == "Train from Brussel-Noord/Bruxelles-Nord to Brussel-Zuid/Bruxelles-Midi"
        )
        assert result["data"] == {
            CONF_STATION_FROM: "Brussel-Noord/Bruxelles-Nord",
            CONF_STATION_LIVE: "Brussel-Centraal/Bruxelles-Central",
            CONF_STATION_TO: "Brussel-Zuid/Bruxelles-Midi",
        }


@pytest.mark.parametrize(
    "user_input",
    [
        {
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        }
    ],
)
async def test_step_import_abort_if_already_setup(
    hass: HomeAssistant, user_input: dict | None
) -> None:
    """Test starting a flow by user which filled in data for connection for already existing connection."""
    MockConfigEntry(
        domain=DOMAIN,
        data=user_input,
        unique_id=f"{user_input[CONF_STATION_FROM]}-{user_input[CONF_STATION_TO]}",
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.nmbs.iRail.get_stations",
        wraps=mock_station_response,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=user_input,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "user_input",
    [
        {
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_LIVE: DUMMY_DATA["STAT_BRUSSELS_CENTRAL"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        },
    ],
)
async def test_unavailable_api_import(
    hass: HomeAssistant, user_input: dict | None
) -> None:
    """Test starting a flow by import and api is unavailable."""
    with patch(
        "homeassistant.components.nmbs.iRail.get_stations",
        wraps=mock_api_unavailable,
    ):
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
        )

        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "api_unavailable"
