"""Tests for the LCN config flow."""

from unittest.mock import patch

from pypck.connection import PchkAuthenticationError, PchkLicenseError
import pytest

from homeassistant import config_entries
from homeassistant.components.lcn.const import CONF_DIM_MODE, CONF_SK_NUM_TRIES, DOMAIN
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

IMPORT_DATA = {
    CONF_HOST: "pchk",
    CONF_IP_ADDRESS: "127.0.0.1",
    CONF_PORT: 4114,
    CONF_USERNAME: "lcn",
    CONF_PASSWORD: "lcn",
    CONF_SK_NUM_TRIES: 0,
    CONF_DIM_MODE: "STEPS200",
    CONF_DEVICES: [],
    CONF_ENTITIES: [],
}


async def test_step_import(hass: HomeAssistant) -> None:
    """Test for import step."""

    with (
        patch("pypck.connection.PchkConnectionManager.async_connect"),
        patch("homeassistant.components.lcn.async_setup", return_value=True),
        patch("homeassistant.components.lcn.async_setup_entry", return_value=True),
    ):
        data = IMPORT_DATA.copy()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "pchk"
        assert result["data"] == IMPORT_DATA


async def test_step_import_existing_host(hass: HomeAssistant) -> None:
    """Test for update of config_entry if imported host already exists."""

    # Create config entry and add it to hass
    mock_data = IMPORT_DATA.copy()
    mock_data.update({CONF_SK_NUM_TRIES: 3, CONF_DIM_MODE: 50})
    mock_entry = MockConfigEntry(domain=DOMAIN, data=mock_data)
    mock_entry.add_to_hass(hass)
    # Initialize a config flow with different data but same host address
    with patch("pypck.connection.PchkConnectionManager.async_connect"):
        imported_data = IMPORT_DATA.copy()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=imported_data
        )
        await hass.async_block_till_done()

        # Check if config entry was updated
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "existing_configuration_updated"
        assert mock_entry.source == config_entries.SOURCE_IMPORT
        assert mock_entry.data == IMPORT_DATA


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (PchkAuthenticationError, "authentication_error"),
        (PchkLicenseError, "license_error"),
        (TimeoutError, "connection_timeout"),
    ],
)
async def test_step_import_error(hass: HomeAssistant, error, reason) -> None:
    """Test for error in import is handled correctly."""
    with patch(
        "pypck.connection.PchkConnectionManager.async_connect", side_effect=error
    ):
        data = IMPORT_DATA.copy()
        data.update({CONF_HOST: "pchk"})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == reason
