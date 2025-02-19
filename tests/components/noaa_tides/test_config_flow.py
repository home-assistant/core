"""Tests for the NOAA Tides config flow."""

from unittest.mock import patch

from noaa_coops.station import Station
import pytest
from requests.exceptions import ConnectionError

from homeassistant import config_entries
from homeassistant.components.noaa_tides.const import (
    CONF_STATION_ID,
    DOMAIN,
    TIMEZONES,
    UNIT_SYSTEMS,
)
from homeassistant.const import CONF_TIME_ZONE, CONF_UNIT_SYSTEM
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import PlatformNotReady

from tests.common import MockConfigEntry

VALID_STATION_ID = "8518750"
VALID_STATION_NAME = "The Battery, NY"

INVALID_STATION_ID = "FAKE_ID"


async def test_import(hass: HomeAssistant) -> None:
    """Test import from yaml."""

    def mock_get_metadata(self: Station):
        self.name = VALID_STATION_NAME

    with patch.object(Station, "get_metadata", mock_get_metadata):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_STATION_ID: VALID_STATION_ID,
                CONF_UNIT_SYSTEM: UNIT_SYSTEMS[0],
                CONF_TIME_ZONE: TIMEZONES[1],
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{VALID_STATION_NAME} ({VALID_STATION_ID})"
    assert result["data"][CONF_STATION_ID] == VALID_STATION_ID
    assert result["options"].get(CONF_UNIT_SYSTEM) == UNIT_SYSTEMS[0]
    assert result["options"].get(CONF_TIME_ZONE) == TIMEZONES[1]
    assert result["result"].unique_id == f"{VALID_STATION_ID.lower()}"


async def test_user(hass: HomeAssistant) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    def mock_get_metadata(self: Station):
        self.name = VALID_STATION_NAME

    with patch.object(Station, "get_metadata", mock_get_metadata):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_STATION_ID: VALID_STATION_ID,
                CONF_UNIT_SYSTEM: UNIT_SYSTEMS[0],
                CONF_TIME_ZONE: TIMEZONES[1],
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{VALID_STATION_NAME} ({VALID_STATION_ID})"
    assert result["data"][CONF_STATION_ID] == VALID_STATION_ID
    assert result["options"].get(CONF_UNIT_SYSTEM) == UNIT_SYSTEMS[0]
    assert result["options"].get(CONF_TIME_ZONE) == TIMEZONES[1]
    assert result["result"].unique_id == f"{VALID_STATION_ID.lower()}"


async def test_user_with_invalid_station_id(hass: HomeAssistant) -> None:
    """Test user config with invalid Station ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    def mock_get_metadata(self: Station):
        raise KeyError

    with patch.object(Station, "get_metadata", mock_get_metadata):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_STATION_ID: INVALID_STATION_ID}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if the Station ID is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATION_ID: VALID_STATION_ID},
        unique_id=f"{VALID_STATION_ID.lower()}",
    ).add_to_hass(hass)

    with patch("noaa_coops.station.Station.__init__", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_STATION_ID: VALID_STATION_ID},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_abort_on_connection_error(hass: HomeAssistant) -> None:
    """Test we abort of we have errors during connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    def mock_get_metadata(self: Station):
        raise ConnectionError

    with (
        pytest.raises(PlatformNotReady),
        patch.object(Station, "get_metadata", mock_get_metadata),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_STATION_ID: VALID_STATION_ID}
        )


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test we can edit options."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATION_ID: VALID_STATION_ID},
        options={
            CONF_TIME_ZONE: TIMEZONES[0],
            CONF_UNIT_SYSTEM: UNIT_SYSTEMS[0],
        },
        unique_id=f"{VALID_STATION_ID.lower()}",
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    def mock_get_metadata(self: Station):
        self.name = VALID_STATION_NAME

    with (
        patch.object(Station, "get_metadata", mock_get_metadata),
        patch(
            "homeassistant.components.noaa_tides.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_TIME_ZONE: TIMEZONES[1],
                CONF_UNIT_SYSTEM: UNIT_SYSTEMS[1],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_TIME_ZONE: TIMEZONES[1],
        CONF_UNIT_SYSTEM: UNIT_SYSTEMS[1],
    }
    assert len(mock_setup_entry.mock_calls) == 1
