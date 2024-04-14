"""Define tests for the Sabnzbd config flow."""

from unittest.mock import AsyncMock, patch

from pysabnzbd import SabnzbdApiException
import pytest

from homeassistant import config_entries
from homeassistant.components.sabnzbd import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

VALID_CONFIG = {
    CONF_NAME: "Sabnzbd",
    CONF_API_KEY: "edc3eee7330e4fdda04489e3fbc283d0",
    CONF_URL: "http://localhost:8080",
}

VALID_CONFIG_OLD = {
    CONF_NAME: "Sabnzbd",
    CONF_API_KEY: "edc3eee7330e4fdda04489e3fbc283d0",
    CONF_HOST: "localhost",
    CONF_PORT: 8080,
    CONF_SSL: False,
}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_create_entry(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sabnzbd.sab.SabnzbdApi.check_available",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "edc3eee7330e"
        assert result2["data"] == {
            CONF_API_KEY: "edc3eee7330e4fdda04489e3fbc283d0",
            CONF_NAME: "Sabnzbd",
            CONF_URL: "http://localhost:8080",
        }
        assert len(mock_setup_entry.mock_calls) == 1


async def test_auth_error(hass: HomeAssistant) -> None:
    """Test that the user step fails."""
    with patch(
        "homeassistant.components.sabnzbd.sab.SabnzbdApi.check_available",
        side_effect=SabnzbdApiException("Some error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["errors"] == {"base": "cannot_connect"}


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test the import configuration flow."""
    with patch(
        "homeassistant.components.sabnzbd.sab.SabnzbdApi.check_available",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=VALID_CONFIG_OLD,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "edc3eee7330e"
        assert result["data"][CONF_NAME] == "Sabnzbd"
        assert result["data"][CONF_API_KEY] == "edc3eee7330e4fdda04489e3fbc283d0"
        assert result["data"][CONF_HOST] == "localhost"
        assert result["data"][CONF_PORT] == 8080
        assert result["data"][CONF_SSL] is False
