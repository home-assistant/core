"""Test the NMBS config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.nmbs.const import (
    CONF_STATION_FROM,
    CONF_STATION_LIVE,
    CONF_STATION_TO,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DUMMY_DATA: dict[str, Any] = {
    "STAT_BRUSSELS_NORTH": "Brussel-Noord/Bruxelles-Nord",
    "STAT_BRUSSELS_CENTRAL": "Brussel-Centraal/Bruxelles-Central",
    "STAT_BRUSSELS_SOUTH": "Brussel-Zuid/Bruxelles-Midi",
}


async def test_full_flow(
    hass: HomeAssistant, mock_nmbs_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["title"]
        == "Train from Brussel-Noord/Bruxelles-Nord to Brussel-Zuid/Bruxelles-Midi"
    )
    assert result["data"] == {
        CONF_STATION_FROM: "Brussel-Noord/Bruxelles-Nord",
        CONF_STATION_TO: "Brussel-Zuid/Bruxelles-Midi",
    }
    assert (
        result["result"].unique_id
        == "Brussel-Noord/Bruxelles-Nord_Brussel-Zuid/Bruxelles-Midi"
    )


async def test_same_station(
    hass: HomeAssistant, mock_nmbs_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test selecting the same station."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "same_station"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_abort_if_exists(
    hass: HomeAssistant, mock_nmbs_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test aborting the flow if the entry already exists."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_unavailable_api(
    hass: HomeAssistant, mock_nmbs_client: AsyncMock
) -> None:
    """Test starting a flow by user and api is unavailable."""
    mock_nmbs_client.get_stations.return_value = -1
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "api_unavailable"


async def test_import(
    hass: HomeAssistant, mock_nmbs_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test starting a flow by user which filled in data for connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_LIVE: DUMMY_DATA["STAT_BRUSSELS_CENTRAL"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        },
    )

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
    assert (
        result["result"].unique_id
        == "Brussel-Noord/Bruxelles-Nord_Brussel-Zuid/Bruxelles-Midi"
    )


async def test_step_import_abort_if_already_setup(
    hass: HomeAssistant, mock_nmbs_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test starting a flow by user which filled in data for connection for already existing connection."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_unavailable_api_import(
    hass: HomeAssistant, mock_nmbs_client: AsyncMock
) -> None:
    """Test starting a flow by import and api is unavailable."""
    mock_nmbs_client.get_stations.return_value = -1
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_LIVE: DUMMY_DATA["STAT_BRUSSELS_CENTRAL"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "api_unavailable"


@pytest.mark.parametrize(
    ("config", "reason"),
    [
        (
            {
                CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
                CONF_STATION_TO: "Utrecht Centraal",
            },
            "invalid_station",
        ),
        (
            {
                CONF_STATION_FROM: "Utrecht Centraal",
                CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
            },
            "invalid_station",
        ),
        (
            {
                CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
                CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            },
            "same_station",
        ),
    ],
)
async def test_invalid_station_name(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    config: dict[str, Any],
    reason: str,
) -> None:
    """Test importing invalid YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
