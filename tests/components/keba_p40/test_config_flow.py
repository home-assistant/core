"""Tests for the KEBA P40 config flow."""

from unittest.mock import AsyncMock

from keba_kecontact_p40 import KebaP40AuthError, KebaP40ConnectionError, KebaP40Error
import pytest

from homeassistant.components.keba_p40.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {CONF_HOST: "1.2.3.4", CONF_PORT: 8443, CONF_PASSWORD: "hunter2"}


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test a successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garage"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == "21900042"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (KebaP40AuthError, "invalid_auth"),
        (KebaP40ConnectionError, "cannot_connect"),
        (KebaP40Error, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    error: type[Exception],
    expected: str,
) -> None:
    """Test the user flow surfaces errors then recovers."""
    mock_client.login.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    mock_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort if the wallbox is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_no_wallbox(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test the user flow handles an empty wallbox list."""
    mock_client.get_wallboxes.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_wallbox"}
