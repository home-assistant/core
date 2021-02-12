"""Define tests for the AEMET OpenData config flow."""

from unittest.mock import patch

import requests_mock

from homeassistant import data_entry_flow
from homeassistant.components.aemet.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    SOURCE_USER,
)
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
import homeassistant.util.dt as dt_util

from .util import aemet_requests_mock

from tests.common import MockConfigEntry

CONFIG = {
    CONF_NAME: "aemet",
    CONF_API_KEY: "foo",
    CONF_LATITUDE: 40.30403754,
    CONF_LONGITUDE: -3.72935236,
}


async def test_form(hass):
    """Test that the form is served with valid input."""

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    with patch("homeassistant.util.dt.now", return_value=now), patch(
        "homeassistant.util.dt.utcnow", return_value=now
    ), requests_mock.mock() as _m:
        aemet_requests_mock(_m)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == SOURCE_USER
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        await hass.async_block_till_done()

        conf_entries = hass.config_entries.async_entries(DOMAIN)
        entry = conf_entries[0]
        assert entry.state == ENTRY_STATE_LOADED

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == CONFIG[CONF_NAME]
        assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LATITUDE]
        assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LONGITUDE]
        assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]


async def test_form_duplicated_id(hass):
    """Test that the options form."""

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    with patch("homeassistant.util.dt.now", return_value=now), patch(
        "homeassistant.util.dt.utcnow", return_value=now
    ), requests_mock.mock() as _m:
        aemet_requests_mock(_m)

        entry = MockConfigEntry(domain=DOMAIN, unique_id="aemet_unique_id", data=CONFIG)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state == ENTRY_STATE_LOADED

        entry_dup = MockConfigEntry(
            domain=DOMAIN, unique_id="aemet_unique_id", data=CONFIG
        )
        entry_dup.add_to_hass(hass)

        await hass.config_entries.async_unload(entry_dup.entry_id)
        await hass.async_block_till_done()
        assert entry_dup.state == ENTRY_STATE_NOT_LOADED


async def test_form_api_offline(hass):
    """Test setting up with api call error."""

    with requests_mock.mock() as _m:
        _m.get(
            "https://opendata.aemet.es/opendata/api/observacion/convencional/todas",
            text="",
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "invalid_api_key"}
