"""Tests for the OpenRGB config flow."""

from unittest.mock import patch

from openrgb.utils import OpenRGBDisconnected, SDKVersionError
import pytest

from homeassistant.components.openrgb.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry", "mock_openrgb_client")
async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6742},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenRGB (127.0.0.1:6742)"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6742,
    }


@pytest.mark.parametrize(
    ("exception", "error_key"),
    [
        (ConnectionRefusedError, "cannot_connect"),
        (OpenRGBDisconnected, "cannot_connect"),
        (SDKVersionError, "cannot_connect"),
        (RuntimeError("Test error"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_openrgb_client")
async def test_user_flow_errors(
    hass: HomeAssistant, exception: Exception, error_key: str
) -> None:
    """Test user flow with various errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.openrgb.config_flow.OpenRGBClient",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6742},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error_key}


@pytest.mark.usefixtures("mock_setup_entry", "mock_openrgb_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6742},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
