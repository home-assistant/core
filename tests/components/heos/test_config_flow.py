"""Tests for the Heos config flow module."""

from pyheos import CommandFailedError, HeosError
import pytest

from homeassistant.components import heos, ssdp
from homeassistant.components.heos.const import DOMAIN
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_flow_aborts_already_setup(hass: HomeAssistant, config_entry) -> None:
    """Test flow aborts when entry already setup."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_no_host_shows_form(hass: HomeAssistant) -> None:
    """Test form is shown when host not provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_cannot_connect_shows_error_form(hass: HomeAssistant, controller) -> None:
    """Test form is shown with error when cannot connect."""
    controller.connect.side_effect = HeosError()
    result = await hass.config_entries.flow.async_init(
        heos.DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "127.0.0.1"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"][CONF_HOST] == "cannot_connect"
    assert controller.connect.call_count == 1
    assert controller.disconnect.call_count == 1


async def test_create_entry_when_host_valid(hass: HomeAssistant, controller) -> None:
    """Test result type is create entry when host is valid."""
    data = {CONF_HOST: "127.0.0.1"}

    result = await hass.config_entries.flow.async_init(
        heos.DOMAIN, context={"source": SOURCE_USER}, data=data
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN
    assert result["title"] == "HEOS System (via 127.0.0.1)"
    assert result["data"] == data
    assert controller.connect.call_count == 2  # Also called in async_setup_entry
    assert controller.disconnect.call_count == 1


async def test_create_entry_when_friendly_name_valid(
    hass: HomeAssistant, controller
) -> None:
    """Test result type is create entry when friendly name is valid."""
    hass.data[DOMAIN] = {"Office (127.0.0.1)": "127.0.0.1"}
    data = {CONF_HOST: "Office (127.0.0.1)"}

    result = await hass.config_entries.flow.async_init(
        heos.DOMAIN, context={"source": SOURCE_USER}, data=data
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN
    assert result["title"] == "HEOS System (via 127.0.0.1)"
    assert result["data"] == {CONF_HOST: "127.0.0.1"}
    assert controller.connect.call_count == 2  # Also called in async_setup_entry
    assert controller.disconnect.call_count == 1
    assert DOMAIN not in hass.data


async def test_discovery_shows_create_form(
    hass: HomeAssistant,
    controller,
    discovery_data: ssdp.SsdpServiceInfo,
    discovery_data_bedroom: ssdp.SsdpServiceInfo,
) -> None:
    """Test discovery shows form to confirm setup."""

    # Single discovered host shows form for user to finish setup.
    result = await hass.config_entries.flow.async_init(
        heos.DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data
    )
    assert hass.data[DOMAIN] == {"Office (127.0.0.1)": "127.0.0.1"}
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Subsequent discovered hosts append to discovered hosts and abort.
    result = await hass.config_entries.flow.async_init(
        heos.DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data_bedroom
    )
    assert hass.data[DOMAIN] == {
        "Office (127.0.0.1)": "127.0.0.1",
        "Bedroom (127.0.0.2)": "127.0.0.2",
    }
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_discovery_flow_aborts_already_setup(
    hass: HomeAssistant, controller, discovery_data: ssdp.SsdpServiceInfo, config_entry
) -> None:
    """Test discovery flow aborts when entry already setup."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reconfigure_validates_and_updates_config(
    hass: HomeAssistant, config_entry, controller
) -> None:
    """Test reconfigure validates host and successfully updates."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert config_entry.data[CONF_HOST] == "127.0.0.1"

    # Test reconfigure initially shows form with current host value.
    host = next(
        key.default() for key in result["data_schema"].schema if key == CONF_HOST
    )
    assert host == "127.0.0.1"
    assert result["errors"] == {}
    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM

    # Test reconfigure successfully updates.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.2"},
    )
    assert controller.connect.call_count == 2  # Also called when entry reloaded
    assert controller.disconnect.call_count == 1
    assert config_entry.data == {CONF_HOST: "127.0.0.2"}
    assert config_entry.unique_id == DOMAIN
    assert result["reason"] == "reconfigure_successful"
    assert result["type"] is FlowResultType.ABORT


async def test_reconfigure_cannot_connect_recovers(
    hass: HomeAssistant, config_entry, controller
) -> None:
    """Test reconfigure cannot connect and recovers."""
    controller.connect.side_effect = HeosError()
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert config_entry.data[CONF_HOST] == "127.0.0.1"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.2"},
    )

    assert controller.connect.call_count == 1
    assert controller.disconnect.call_count == 1
    host = next(
        key.default() for key in result["data_schema"].schema if key == CONF_HOST
    )
    assert host == "127.0.0.2"
    assert result["errors"][CONF_HOST] == "cannot_connect"
    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM

    # Test reconfigure recovers and successfully updates.
    controller.connect.side_effect = None
    controller.connect.reset_mock()
    controller.disconnect.reset_mock()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.2"},
    )
    assert controller.connect.call_count == 2  # Also called when entry reloaded
    assert controller.disconnect.call_count == 1
    assert config_entry.data == {CONF_HOST: "127.0.0.2"}
    assert config_entry.unique_id == DOMAIN
    assert result["reason"] == "reconfigure_successful"
    assert result["type"] is FlowResultType.ABORT


@pytest.mark.parametrize(
    ("error", "expected_error_key"),
    [
        (
            CommandFailedError("sign_in", "Invalid credentials", 6),
            "invalid_auth",
        ),
        (
            CommandFailedError("sign_in", "User not logged in", 8),
            "invalid_auth",
        ),
        (CommandFailedError("sign_in", "user not found", 10), "invalid_auth"),
        (CommandFailedError("sign_in", "System error", 12), "unknown"),
        (HeosError(), "unknown"),
    ],
)
async def test_options_flow_signs_in(
    hass: HomeAssistant,
    config_entry,
    controller,
    error: HeosError,
    expected_error_key: str,
) -> None:
    """Test options flow signs-in with entered credentials."""
    config_entry.add_to_hass(hass)

    # Start the options flow. Entry has not current options.
    assert CONF_USERNAME not in config_entry.options
    assert CONF_PASSWORD not in config_entry.options
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["step_id"] == "init"
    assert result["errors"] == {}
    assert result["type"] is FlowResultType.FORM

    # Invalid credentials, system error, or unexpected error.
    user_input = {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    controller.sign_in.side_effect = error
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert controller.sign_in.call_count == 1
    assert controller.sign_out.call_count == 0
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": expected_error_key}
    assert result["type"] is FlowResultType.FORM

    # Valid credentials signs-in and creates entry
    controller.sign_in.reset_mock()
    controller.sign_in.side_effect = None
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert controller.sign_in.call_count == 1
    assert controller.sign_out.call_count == 0
    assert result["data"] == user_input
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_signs_out(
    hass: HomeAssistant, config_entry, controller
) -> None:
    """Test options flow signs-out when credentials cleared."""
    config_entry.add_to_hass(hass)

    # Start the options flow. Entry has not current options.
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["step_id"] == "init"
    assert result["errors"] == {}
    assert result["type"] is FlowResultType.FORM

    # Fail to sign-out, show error
    user_input = {}
    controller.sign_out.side_effect = HeosError()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert controller.sign_in.call_count == 0
    assert controller.sign_out.call_count == 1
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": "unknown"}
    assert result["type"] is FlowResultType.FORM

    # Clear credentials
    controller.sign_out.reset_mock()
    controller.sign_out.side_effect = None
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert controller.sign_in.call_count == 0
    assert controller.sign_out.call_count == 1
    assert result["data"] == user_input
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("user_input", "expected_errors"),
    [
        ({CONF_USERNAME: "user"}, {CONF_PASSWORD: "password_missing"}),
        ({CONF_PASSWORD: "pass"}, {CONF_USERNAME: "username_missing"}),
    ],
)
async def test_options_flow_missing_one_param_recovers(
    hass: HomeAssistant,
    config_entry,
    controller,
    user_input: dict[str, str],
    expected_errors: dict[str, str],
) -> None:
    """Test options flow signs-in after recovering from only username or password being entered."""
    config_entry.add_to_hass(hass)

    # Start the options flow. Entry has not current options.
    assert CONF_USERNAME not in config_entry.options
    assert CONF_PASSWORD not in config_entry.options
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["step_id"] == "init"
    assert result["errors"] == {}
    assert result["type"] is FlowResultType.FORM

    # Enter only username or password
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert result["step_id"] == "init"
    assert result["errors"] == expected_errors
    assert result["type"] is FlowResultType.FORM

    # Enter valid credentials
    user_input = {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert controller.sign_in.call_count == 1
    assert controller.sign_out.call_count == 0
    assert result["data"] == user_input
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("error", "expected_error_key"),
    [
        (
            CommandFailedError("sign_in", "Invalid credentials", 6),
            "invalid_auth",
        ),
        (
            CommandFailedError("sign_in", "User not logged in", 8),
            "invalid_auth",
        ),
        (CommandFailedError("sign_in", "user not found", 10), "invalid_auth"),
        (CommandFailedError("sign_in", "System error", 12), "unknown"),
        (HeosError(), "unknown"),
    ],
)
async def test_reauth_signs_in_aborts(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller,
    error: HeosError,
    expected_error_key: str,
) -> None:
    """Test reauth flow signs-in with entered credentials and aborts."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}
    assert result["type"] is FlowResultType.FORM

    # Invalid credentials, system error, or unexpected error.
    user_input = {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    controller.sign_in.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert controller.sign_in.call_count == 1
    assert controller.sign_out.call_count == 0
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error_key}
    assert result["type"] is FlowResultType.FORM

    # Valid credentials signs-in, updates options, and aborts
    controller.sign_in.reset_mock()
    controller.sign_in.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert controller.sign_in.call_count == 1
    assert controller.sign_out.call_count == 0
    assert config_entry.options[CONF_USERNAME] == user_input[CONF_USERNAME]
    assert config_entry.options[CONF_PASSWORD] == user_input[CONF_PASSWORD]
    assert result["reason"] == "reauth_successful"
    assert result["type"] is FlowResultType.ABORT


async def test_reauth_signs_out(hass: HomeAssistant, config_entry, controller) -> None:
    """Test reauth flow signs-out when credentials cleared and aborts."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}
    assert result["type"] is FlowResultType.FORM

    # Fail to sign-out, show error
    user_input = {}
    controller.sign_out.side_effect = HeosError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert controller.sign_in.call_count == 0
    assert controller.sign_out.call_count == 1
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "unknown"}
    assert result["type"] is FlowResultType.FORM

    # Cleared credentials signs-out, updates options, and aborts
    controller.sign_out.reset_mock()
    controller.sign_out.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert controller.sign_in.call_count == 0
    assert controller.sign_out.call_count == 1
    assert CONF_USERNAME not in config_entry.options
    assert CONF_PASSWORD not in config_entry.options
    assert result["reason"] == "reauth_successful"
    assert result["type"] is FlowResultType.ABORT


@pytest.mark.parametrize(
    ("user_input", "expected_errors"),
    [
        ({CONF_USERNAME: "user"}, {CONF_PASSWORD: "password_missing"}),
        ({CONF_PASSWORD: "pass"}, {CONF_USERNAME: "username_missing"}),
    ],
)
async def test_reauth_flow_missing_one_param_recovers(
    hass: HomeAssistant,
    config_entry,
    controller,
    user_input: dict[str, str],
    expected_errors: dict[str, str],
) -> None:
    """Test reauth flow signs-in after recovering from only username or password being entered."""
    config_entry.add_to_hass(hass)

    # Start the options flow. Entry has not current options.
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}
    assert result["type"] is FlowResultType.FORM

    # Enter only username or password
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == expected_errors
    assert result["type"] is FlowResultType.FORM

    # Enter valid credentials
    user_input = {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert controller.sign_in.call_count == 1
    assert controller.sign_out.call_count == 0
    assert config_entry.options[CONF_USERNAME] == user_input[CONF_USERNAME]
    assert config_entry.options[CONF_PASSWORD] == user_input[CONF_PASSWORD]
    assert result["reason"] == "reauth_successful"
    assert result["type"] is FlowResultType.ABORT
