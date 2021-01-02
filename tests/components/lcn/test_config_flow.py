"""Tests for the LCN config flow."""
from unittest.mock import patch

from pypck.connection import PchkAuthenticationError, PchkLicenseError
import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.lcn.const import CONF_DIM_MODE, CONF_SK_NUM_TRIES, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry

IMPORT_DATA = {
    CONF_IP_ADDRESS: "127.0.0.1",
    CONF_PORT: 4114,
    CONF_USERNAME: "lcn",
    CONF_PASSWORD: "lcn",
    CONF_SK_NUM_TRIES: 0,
    CONF_DIM_MODE: "STEPS200",
}


async def test_step_import(hass):
    """Test for import step."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch("pypck.connection.PchkConnectionManager.async_connect"), patch(
        "homeassistant.components.lcn.async_setup", return_value=True
    ), patch("homeassistant.components.lcn.async_setup_entry", return_value=True):
        data = IMPORT_DATA.copy()
        data.update({CONF_HOST: "pchk"})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "pchk"
        assert result["data"] == IMPORT_DATA


async def test_step_import_existing_host(hass):
    """Test for update of config_entry if imported host already exists."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    mock_entry = MockConfigEntry()
    with patch("pypck.connection.PchkConnectionManager.async_connect"), patch(
        "homeassistant.components.lcn.config_flow.get_config_entry",
        return_value=mock_entry,
    ):
        data = IMPORT_DATA.copy()
        data.update({CONF_HOST: "pchk"})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "existing_configuration_updated"
        assert mock_entry.source == config_entries.SOURCE_IMPORT
        assert mock_entry.data == IMPORT_DATA


@pytest.mark.parametrize(
    "error,reason",
    [
        (PchkAuthenticationError, "authentication_error"),
        (PchkLicenseError, "license_error"),
        (TimeoutError, "connection_timeout"),
    ],
)
async def test_step_import_error(hass, error, reason):
    """Test for authentication error is handled correctly."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "pypck.connection.PchkConnectionManager.async_connect", side_effect=error
    ):
        data = IMPORT_DATA.copy()
        data.update({CONF_HOST: "pchk"})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == reason
