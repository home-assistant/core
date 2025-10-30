"""Tests for the Vivotek config flow."""

from unittest.mock import patch

from libpyvivotek.vivotek import VivotekCameraError
import pytest

from homeassistant import config_entries
from homeassistant.components.vivotek.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_DATA

from tests.common import MockConfigEntry


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
    assert result.get("title") == TEST_DATA[CONF_NAME]
    assert result.get("data") == TEST_DATA


async def test_step_reconfigure_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_setup_entry
) -> None:
    """Test we handle connection error during reconfigure."""
    mock_config_entry.add_to_hass(hass)  # This is the key change

    with patch(
        "libpyvivotek.VivotekCamera.get_mac",
        side_effect=VivotekCameraError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": "reconfigure",
                "entry_id": mock_config_entry.entry_id,
            },
            data=TEST_DATA,
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"
    assert result.get("errors") == {"base": "cannot_connect"}


async def test_step_reconfigure_unexpected_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_setup_entry
) -> None:
    """Test we handle unexpected error during reconfigure."""
    mock_config_entry.add_to_hass(hass)  # Add this line

    with patch(
        "libpyvivotek.VivotekCamera.get_mac",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": "reconfigure",
                "entry_id": mock_config_entry.entry_id,
            },
            data=TEST_DATA,
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"
    assert result.get("errors") == {"base": "unknown"}


async def test_step_reconfigure_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_setup_entry
) -> None:
    """Test reconfiguration flow success."""
    mock_config_entry.add_to_hass(hass)

    new_data = {
        **TEST_DATA,
        CONF_IP_ADDRESS: "5.6.7.8",  # Changed IP
        CONF_PORT: "8080",  # Changed port
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": "reconfigure",
            "entry_id": mock_config_entry.entry_id,
        },
        data=new_data,
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert mock_config_entry.data == new_data
