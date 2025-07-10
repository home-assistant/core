"""Tests for the Heos config flow module."""

from typing import Any

from pyheos import (
    CommandAuthenticationError,
    CommandFailedError,
    ConnectionState,
    HeosError,
    HeosHost,
    HeosSystem,
    NetworkType,
)
import pytest

from homeassistant.components.heos.const import DOMAIN
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_SSDP,
    SOURCE_USER,
    ConfigEntryState,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from . import MockHeos

from tests.common import MockConfigEntry


async def test_flow_aborts_already_setup(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
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


async def test_cannot_connect_shows_error_form(
    hass: HomeAssistant, controller: MockHeos
) -> None:
    """Test form is shown with error when cannot connect."""
    controller.connect.side_effect = HeosError()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "127.0.0.1"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    errors = result["errors"]
    assert errors is not None
    assert errors[CONF_HOST] == "cannot_connect"
    assert controller.connect.call_count == 1
    assert controller.disconnect.call_count == 1


async def test_create_entry_when_host_valid(
    hass: HomeAssistant, controller: MockHeos
) -> None:
    """Test result type is create entry when host is valid."""
    data = {CONF_HOST: "127.0.0.1"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=data
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN
    assert result["title"] == "HEOS System"
    assert result["data"] == data
    assert controller.connect.call_count == 2  # Also called in async_setup_entry
    assert controller.disconnect.call_count == 1


async def test_manual_setup_with_discovery_in_progress(
    hass: HomeAssistant,
    discovery_data: SsdpServiceInfo,
    controller: MockHeos,
    system: HeosSystem,
) -> None:
    """Test user can manually set up when discovery is in progress."""
    # Single discovered, selects preferred host, shows confirm
    controller.get_system_info.return_value = system
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_discovery"

    # Setup manually
    user_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert user_result["type"] is FlowResultType.FORM
    user_result = await hass.config_entries.flow.async_configure(
        user_result["flow_id"], user_input={CONF_HOST: "127.0.0.1"}
    )
    assert user_result["type"] is FlowResultType.CREATE_ENTRY

    # Discovery flow is removed
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_discovery(
    hass: HomeAssistant,
    discovery_data: SsdpServiceInfo,
    discovery_data_bedroom: SsdpServiceInfo,
    controller: MockHeos,
    system: HeosSystem,
) -> None:
    """Test discovery shows form to confirm, then creates entry."""
    # Single discovered, selects preferred host, shows confirm
    controller.get_system_info.return_value = system
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data_bedroom
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_discovery"
    assert controller.connect.call_count == 1
    assert controller.get_system_info.call_count == 1
    assert controller.disconnect.call_count == 1

    # Subsequent discovered hosts abort.
    subsequent_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data
    )
    assert subsequent_result["type"] is FlowResultType.ABORT
    assert subsequent_result["reason"] == "already_in_progress"

    # Confirm set up
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN
    assert result["title"] == "HEOS System"
    assert result["data"] == {CONF_HOST: "127.0.0.1"}


async def test_discovery_flow_aborts_already_setup(
    hass: HomeAssistant,
    discovery_data_bedroom: SsdpServiceInfo,
    config_entry: MockConfigEntry,
    controller: MockHeos,
) -> None:
    """Test discovery flow aborts when entry already setup and hosts didn't change."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.data[CONF_HOST] == "127.0.0.1"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data_bedroom
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    assert controller.get_system_info.call_count == 0
    assert config_entry.data[CONF_HOST] == "127.0.0.1"


async def test_discovery_aborts_same_system(
    hass: HomeAssistant,
    discovery_data_bedroom: SsdpServiceInfo,
    controller: MockHeos,
    config_entry: MockConfigEntry,
    system: HeosSystem,
) -> None:
    """Test discovery does not update when current host is part of discovered's system."""
    config_entry.add_to_hass(hass)
    assert config_entry.data[CONF_HOST] == "127.0.0.1"

    controller.get_system_info.return_value = system
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data_bedroom
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    assert controller.get_system_info.call_count == 1
    assert config_entry.data[CONF_HOST] == "127.0.0.1"


async def test_discovery_ignored_aborts(
    hass: HomeAssistant,
    discovery_data: SsdpServiceInfo,
) -> None:
    """Test discovery aborts when ignored."""
    MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, source=SOURCE_IGNORE).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_discovery_fails_to_connect_aborts(
    hass: HomeAssistant, discovery_data: SsdpServiceInfo, controller: MockHeos
) -> None:
    """Test discovery aborts when trying to connect to host."""
    controller.connect.side_effect = HeosError()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    assert controller.connect.call_count == 1
    assert controller.disconnect.call_count == 1


async def test_discovery_updates(
    hass: HomeAssistant,
    discovery_data_bedroom: SsdpServiceInfo,
    controller: MockHeos,
    config_entry: MockConfigEntry,
) -> None:
    """Test discovery updates existing entry."""
    config_entry.add_to_hass(hass)
    assert config_entry.data[CONF_HOST] == "127.0.0.1"

    host = HeosHost("Player", "Model", None, None, "127.0.0.2", NetworkType.WIRED, True)
    controller.get_system_info.return_value = HeosSystem(None, host, [host])
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data_bedroom
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_HOST] == "127.0.0.2"


async def test_reconfigure_validates_and_updates_config(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test reconfigure validates host and successfully updates."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)
    assert config_entry.data[CONF_HOST] == "127.0.0.1"

    # Test reconfigure initially shows form with current host value.
    schema = result["data_schema"]
    assert schema is not None
    host = next(key.default() for key in schema.schema if key == CONF_HOST)
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
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
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
    schema = result["data_schema"]
    assert schema is not None
    host = next(key.default() for key in schema.schema if key == CONF_HOST)
    assert host == "127.0.0.2"
    errors = result["errors"]
    assert errors is not None
    assert errors[CONF_HOST] == "cannot_connect"
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
            CommandAuthenticationError("sign_in", "Invalid credentials", 6),
            "invalid_auth",
        ),
        (CommandFailedError("sign_in", "System error", 12), "unknown"),
        (HeosError(), "unknown"),
    ],
)
async def test_options_flow_signs_in(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    error: HeosError,
    expected_error_key: str,
) -> None:
    """Test options flow signs-in with entered credentials."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    controller.mock_set_connection_state(ConnectionState.CONNECTED)

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
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test options flow signs-out when credentials cleared."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    controller.mock_set_connection_state(ConnectionState.CONNECTED)

    # Start the options flow. Entry has not current options.
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["step_id"] == "init"
    assert result["errors"] == {}
    assert result["type"] is FlowResultType.FORM

    # Fail to sign-out, show error
    user_input: dict[str, Any] = {}
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
    config_entry: MockConfigEntry,
    controller: MockHeos,
    user_input: dict[str, str],
    expected_errors: dict[str, str],
) -> None:
    """Test options flow signs-in after recovering from only username or password being entered."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    controller.mock_set_connection_state(ConnectionState.CONNECTED)

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


async def test_options_flow_sign_in_setup_error_saves(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test options can still be updated when the integration failed to set up."""
    config_entry.add_to_hass(hass)
    controller.get_players.side_effect = ValueError("Unexpected error")
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    # Enter valid credentials
    user_input = {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert controller.sign_in.call_count == 0
    assert controller.sign_out.call_count == 0
    assert config_entry.options == user_input
    assert result["data"] == user_input
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_sign_out_setup_error_saves(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test options can still be cleared when the integration failed to set up."""
    config_entry.add_to_hass(hass)
    controller.get_players.side_effect = ValueError("Unexpected error")
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    # Enter valid credentials
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert controller.sign_in.call_count == 0
    assert controller.sign_out.call_count == 0
    assert config_entry.options == {}
    assert result["data"] == {}
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_sign_in_not_connected_saves(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test options can still be updated when not connected to the HEOS device."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    controller.mock_set_connection_state(ConnectionState.RECONNECTING)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    # Enter valid credentials
    user_input = {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert controller.sign_in.call_count == 0
    assert controller.sign_out.call_count == 0
    assert config_entry.options == user_input
    assert result["data"] == user_input
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_sign_out_not_connected_saves(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test options can still be cleared when not connected to the HEOS device."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    controller.mock_set_connection_state(ConnectionState.RECONNECTING)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    # Enter valid credentials
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert controller.sign_in.call_count == 0
    assert controller.sign_out.call_count == 0
    assert config_entry.options == {}
    assert result["data"] == {}
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("error", "expected_error_key"),
    [
        (
            CommandAuthenticationError("sign_in", "Invalid credentials", 6),
            "invalid_auth",
        ),
        (CommandFailedError("sign_in", "System error", 12), "unknown"),
        (HeosError(), "unknown"),
    ],
)
async def test_reauth_signs_in_aborts(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    error: HeosError,
    expected_error_key: str,
) -> None:
    """Test reauth flow signs-in with entered credentials and aborts."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    controller.mock_set_connection_state(ConnectionState.CONNECTED)
    result = await config_entry.start_reauth_flow(hass)
    assert config_entry.state is ConfigEntryState.LOADED

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


async def test_reauth_signs_out(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test reauth flow signs-out when credentials cleared and aborts."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    controller.mock_set_connection_state(ConnectionState.CONNECTED)
    result = await config_entry.start_reauth_flow(hass)
    assert config_entry.state is ConfigEntryState.LOADED

    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}
    assert result["type"] is FlowResultType.FORM

    # Fail to sign-out, show error
    user_input: dict[str, Any] = {}
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
    config_entry: MockConfigEntry,
    controller: MockHeos,
    user_input: dict[str, str],
    expected_errors: dict[str, str],
) -> None:
    """Test reauth flow signs-in after recovering from only username or password being entered."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    controller.mock_set_connection_state(ConnectionState.CONNECTED)

    # Start the options flow. Entry has not current options.
    result = await config_entry.start_reauth_flow(hass)
    assert config_entry.state is ConfigEntryState.LOADED
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


async def test_reauth_updates_when_not_connected(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test reauth flow signs-in with entered credentials and aborts."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    controller.mock_set_connection_state(ConnectionState.RECONNECTING)

    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}
    assert result["type"] is FlowResultType.FORM

    # Valid credentials signs-in, updates options, and aborts
    user_input = {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert controller.sign_in.call_count == 0
    assert controller.sign_out.call_count == 0
    assert config_entry.options[CONF_USERNAME] == user_input[CONF_USERNAME]
    assert config_entry.options[CONF_PASSWORD] == user_input[CONF_PASSWORD]
    assert result["reason"] == "reauth_successful"
    assert result["type"] is FlowResultType.ABORT


async def test_reauth_clears_when_not_connected(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test reauth flow signs-out with entered credentials and aborts."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    controller.mock_set_connection_state(ConnectionState.RECONNECTING)

    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}
    assert result["type"] is FlowResultType.FORM

    # Valid credentials signs-out, updates options, and aborts
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert controller.sign_in.call_count == 0
    assert controller.sign_out.call_count == 0
    assert config_entry.options == {}
    assert result["reason"] == "reauth_successful"
    assert result["type"] is FlowResultType.ABORT
