"""Define tests for the Sabnzbd config flow."""

from unittest.mock import AsyncMock

from pysabnzbd import SabnzbdApiException
import pytest

from homeassistant import config_entries
from homeassistant.components.sabnzbd import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

VALID_CONFIG = {
    CONF_API_KEY: "edc3eee7330e4fdda04489e3fbc283d0",
    CONF_URL: "http://localhost:8080",
}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_create_entry(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_CONFIG,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "edc3eee7330e"
    assert result["data"] == {
        CONF_API_KEY: "edc3eee7330e4fdda04489e3fbc283d0",
        CONF_URL: "http://localhost:8080",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_auth_error(hass: HomeAssistant, sabnzbd: AsyncMock) -> None:
    """Test when the user step fails and if we can recover."""
    sabnzbd.check_available.side_effect = SabnzbdApiException("Some error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result["errors"] == {"base": "cannot_connect"}

    # reset side effect and check if we can recover
    sabnzbd.check_available.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_CONFIG,
    )
    await hass.async_block_till_done()

    assert "errors" not in result
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "edc3eee7330e"
    assert result["data"] == {
        CONF_API_KEY: "edc3eee7330e4fdda04489e3fbc283d0",
        CONF_URL: "http://localhost:8080",
    }
