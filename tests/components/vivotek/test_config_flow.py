"""Tests for the Vivotek config flow."""

from unittest.mock import patch

from libpyvivotek.vivotek import VivotekCameraError
import pytest

from homeassistant import config_entries
from homeassistant.components.vivotek.camera import DEFAULT_NAME
from homeassistant.components.vivotek.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_DATA


@pytest.fixture(autouse=True)
def mock_test_config():
    """Mock testing the config."""
    with patch(
        "libpyvivotek.VivotekCamera.get_mac",
        return_value="11:22:33:44:55:66",
    ) as mock_test:
        yield mock_test


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {}


async def test_step_user_connection_error(hass: HomeAssistant) -> None:
    """Test we handle connection error."""
    with patch(
        "libpyvivotek.VivotekCamera.get_mac",
        side_effect=VivotekCameraError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=TEST_DATA,
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}


async def test_step_user_unexpected_error(hass: HomeAssistant) -> None:
    """Test we handle unexpected error."""
    with patch(
        "libpyvivotek.VivotekCamera.get_mac",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=TEST_DATA,
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "unknown"}


async def test_step_user_success(hass: HomeAssistant) -> None:
    """Test we handle success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=TEST_DATA,
    )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == DEFAULT_NAME
    assert result.get("data") == TEST_DATA
