"""Define tests for the Sabnzbd config flow."""

from unittest.mock import AsyncMock

from pysabnzbd import SabnzbdApiException
import pytest

from homeassistant import config_entries
from homeassistant.components.sabnzbd.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

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
    assert result["title"] == "localhost"
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
    assert result["title"] == "localhost"
    assert result["data"] == {
        CONF_API_KEY: "edc3eee7330e4fdda04489e3fbc283d0",
        CONF_URL: "http://localhost:8080",
    }


async def test_reconfigure_successful(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring a SABnzbd entry."""
    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: "http://10.10.10.10:8080", CONF_API_KEY: "new_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {
        CONF_URL: "http://10.10.10.10:8080",
        CONF_API_KEY: "new_key",
    }


async def test_reconfigure_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, sabnzbd: AsyncMock
) -> None:
    """Test reconfiguring a SABnzbd entry."""
    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # set side effect and check if error is handled
    sabnzbd.check_available.side_effect = SabnzbdApiException("Some error")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: "http://10.10.10.10:8080", CONF_API_KEY: "new_key"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    # reset side effect and check if we can recover
    sabnzbd.check_available.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: "http://10.10.10.10:8080", CONF_API_KEY: "new_key"},
    )

    assert "errors" not in result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {
        CONF_URL: "http://10.10.10.10:8080",
        CONF_API_KEY: "new_key",
    }


async def test_abort_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that the flow aborts if SABnzbd instance is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_abort_reconfigure_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that the reconfigure flow aborts if SABnzbd instance is already configured."""
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_CONFIG,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
