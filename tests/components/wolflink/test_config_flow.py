"""Test the Wolf SmartSet Service config flow."""

from unittest.mock import patch

from httpx import RequestError
import pytest
from wolf_comm.models import Device
from wolf_comm.token_auth import InvalidAuth

from homeassistant import config_entries
from homeassistant.components.wolflink.const import DEVICE_ID, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import CONFIG

from tests.common import MockConfigEntry

INPUT_CONFIG = {
    CONF_USERNAME: CONFIG[CONF_USERNAME],
    CONF_PASSWORD: CONFIG[CONF_PASSWORD],
}

DEVICE = Device(1234, 5678, "test-device")
SECOND_DEVICE = Device(5678, 9999, "second-device")


async def test_show_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test entry creation auto-adds all devices on the account."""
    with (
        patch(
            "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
            return_value=[DEVICE],
        ),
        patch("homeassistant.components.wolflink.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == CONFIG[CONF_USERNAME]
    assert result["data"] == CONFIG
    assert result["result"].unique_id == CONFIG[CONF_USERNAME].lower()


async def test_create_entry_multiple_devices(hass: HomeAssistant) -> None:
    """Test entry creation with multiple devices on the account."""
    with (
        patch(
            "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
            return_value=[DEVICE, SECOND_DEVICE],
        ),
        patch("homeassistant.components.wolflink.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][DEVICE_ID] == [DEVICE.id, SECOND_DEVICE.id]


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(InvalidAuth, "invalid_auth", id="invalid_auth"),
        pytest.param(RequestError("boom"), "cannot_connect", id="cannot_connect"),
        pytest.param(Exception("boom"), "unknown", id="unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, side_effect: Exception, expected_error: str
) -> None:
    """Test error handling in the user step keeps the form open with errors."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_no_devices_abort(hass: HomeAssistant) -> None:
    """Test we abort if the account has no devices."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices"


async def test_already_configured_aborts(hass: HomeAssistant) -> None:
    """Test entries with the same username can't be configured twice."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data=CONFIG,
        version=2,
        minor_version=2,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
