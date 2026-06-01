"""Test the Wolf SmartSet Service config flow."""

from unittest.mock import patch

from httpcore import ConnectError
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


async def test_show_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_device_step_form(hass: HomeAssistant) -> None:
    """Test we get the device selection step."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        return_value=[DEVICE],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test entry creation from device step."""
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

        result_create_entry = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {DEVICE_ID: ["1234"]},
        )

    assert result_create_entry["type"] is FlowResultType.CREATE_ENTRY
    assert result_create_entry["title"] == CONFIG[CONF_USERNAME]
    assert result_create_entry["data"] == CONFIG
    assert result_create_entry["result"].unique_id == CONFIG[CONF_USERNAME].lower()


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=ConnectError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle unknown exception."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


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


async def test_already_configured_error(hass: HomeAssistant) -> None:
    """Test already configured while creating entry."""
    with (
        patch(
            "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
            return_value=[DEVICE],
        ),
        patch("homeassistant.components.wolflink.async_setup_entry", return_value=True),
    ):
        MockConfigEntry(
            domain=DOMAIN,
            unique_id=CONFIG[CONF_USERNAME].lower(),
            data=CONFIG,
        ).add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

        result_create_entry = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {DEVICE_ID: ["1234"]},
        )

    assert result_create_entry["type"] is FlowResultType.ABORT
    assert result_create_entry["reason"] == "already_configured"


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfigure flow to change selected devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data=CONFIG,
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    second_device = Device(5678, 9999, "second-device")

    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        return_value=[DEVICE, second_device],
    ):
        result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with (
        patch(
            "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
            return_value=[DEVICE, second_device],
        ),
        patch("homeassistant.components.wolflink.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {DEVICE_ID: ["1234", "5678"]},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[DEVICE_ID] == [1234, 5678]


async def test_reconfigure_retries_on_error(hass: HomeAssistant) -> None:
    """Test reconfigure re-shows the form on connection errors so the user can retry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data=CONFIG,
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    # First attempt: fetch fails — expect the reconfigure form re-shown with errors.
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=ConnectError("boom"),
    ):
        result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}

    # User retries: fetch now succeeds — expect the device-selection form.
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        return_value=[DEVICE],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert not result.get("errors")

    # User submits selection: expect successful reconfigure.
    with patch(
        "homeassistant.components.wolflink.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {DEVICE_ID: ["1234"]},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[DEVICE_ID] == [1234]
