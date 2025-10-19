"""Tests for the Vivotek config flow."""

from unittest.mock import patch

from libpyvivotek.vivotek import VivotekCameraError
import pytest

from homeassistant import config_entries
from homeassistant.components.vivotek.const import DOMAIN
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_DATA = {
    CONF_NAME: "Test Camera",
    CONF_IP_ADDRESS: "1.2.3.4",
    CONF_PORT: "80",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "pass1234",
    CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
    "framerate": 2,
    "security_level": "admin",
    "stream_path": "/live.sdp",
}


@pytest.fixture(autouse=True)
def mock_test_config():
    """Mock testing the config."""
    with patch(
        "homeassistant.components.vivotek.config_flow.async_test_config",
        return_value=True,
    ) as mock_test:
        yield mock_test


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_step_user_connection_error(hass: HomeAssistant) -> None:
    """Test we handle connection error."""
    with patch(
        "homeassistant.components.vivotek.config_flow.async_test_config",
        side_effect=VivotekCameraError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=TEST_DATA,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_step_user_unexpected_error(hass: HomeAssistant) -> None:
    """Test we handle unexpected error."""
    with patch(
        "homeassistant.components.vivotek.config_flow.async_test_config",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=TEST_DATA,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_step_user_success(hass: HomeAssistant) -> None:
    """Test we handle success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=TEST_DATA,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DATA[CONF_NAME]
    assert result["data"] == TEST_DATA


@pytest.fixture
async def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch("homeassistant.components.vivotek.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock existing config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=TEST_DATA,
        title="Vivotek Camera",
        unique_id="test_unique_id",
    )


async def test_step_reconfigure_connection_error(
    hass: HomeAssistant, mock_config_entry: config_entries.ConfigEntry, mock_setup_entry
) -> None:
    """Test we handle connection error during reconfigure."""
    mock_config_entry.add_to_hass(hass)  # This is the key change

    with patch(
        "homeassistant.components.vivotek.config_flow.async_test_config",
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_step_reconfigure_unexpected_error(
    hass: HomeAssistant, mock_config_entry: config_entries.ConfigEntry, mock_setup_entry
) -> None:
    """Test we handle unexpected error during reconfigure."""
    mock_config_entry.add_to_hass(hass)  # Add this line

    with patch(
        "homeassistant.components.vivotek.config_flow.async_test_config",
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "unknown"}


async def test_step_reconfigure_success(
    hass: HomeAssistant, mock_config_entry: config_entries.ConfigEntry, mock_setup_entry
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

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == new_data
