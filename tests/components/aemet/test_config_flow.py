"""Define tests for the AEMET OpenData config flow."""
from unittest.mock import MagicMock, patch

import requests_mock

from homeassistant import data_entry_flow
from homeassistant.components.aemet.const import CONF_STATION_UPDATES, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .util import aemet_requests_mock

from tests.common import MockConfigEntry

CONFIG = {
    CONF_NAME: "aemet",
    CONF_API_KEY: "foo",
    CONF_LATITUDE: 40.30403754,
    CONF_LONGITUDE: -3.72935236,
}


async def test_form(hass: HomeAssistant) -> None:
    """Test that the form is served with valid input."""

    with patch(
        "homeassistant.components.aemet.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, requests_mock.mock() as _m:
        aemet_requests_mock(_m)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == SOURCE_USER
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

        await hass.async_block_till_done()

        conf_entries = hass.config_entries.async_entries(DOMAIN)
        entry = conf_entries[0]
        assert entry.state is ConfigEntryState.LOADED

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == CONFIG[CONF_NAME]
        assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LATITUDE]
        assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LONGITUDE]
        assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]

        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_options(hass: HomeAssistant) -> None:
    """Test the form options."""

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    with patch("homeassistant.util.dt.now", return_value=now), patch(
        "homeassistant.util.dt.utcnow", return_value=now
    ), requests_mock.mock() as _m:
        aemet_requests_mock(_m)

        entry = MockConfigEntry(
            domain=DOMAIN, unique_id="40.30403754--3.72935236", data=CONFIG
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_STATION_UPDATES: False}
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert entry.options == {
            CONF_STATION_UPDATES: False,
        }

        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_STATION_UPDATES: True}
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert entry.options == {
            CONF_STATION_UPDATES: True,
        }

        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED


async def test_form_duplicated_id(hass: HomeAssistant) -> None:
    """Test setting up duplicated entry."""

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    with patch("homeassistant.util.dt.now", return_value=now), patch(
        "homeassistant.util.dt.utcnow", return_value=now
    ), requests_mock.mock() as _m:
        aemet_requests_mock(_m)

        entry = MockConfigEntry(
            domain=DOMAIN, unique_id="40.30403754--3.72935236", data=CONFIG
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_form_api_offline(hass: HomeAssistant) -> None:
    """Test setting up with api call error."""
    mocked_aemet = MagicMock()

    mocked_aemet.get_conventional_observation_stations.return_value = None

    with patch(
        "homeassistant.components.aemet.config_flow.AEMET",
        return_value=mocked_aemet,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "invalid_api_key"}
