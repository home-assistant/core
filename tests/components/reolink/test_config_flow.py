"""Test the Reolink config flow."""

import json
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

from aiohttp import ClientSession
from freezegun.api import FrozenDateTimeFactory
import pytest
from reolink_aio.exceptions import (
    ApiError,
    CredentialsInvalidError,
    LoginFirmwareError,
    LoginPrivacyModeError,
    ReolinkError,
)

from homeassistant import config_entries
from homeassistant.components.reolink import DEVICE_UPDATE_INTERVAL
from homeassistant.components.reolink.config_flow import DEFAULT_PROTOCOL
from homeassistant.components.reolink.const import (
    CONF_BC_PORT,
    CONF_SUPPORTS_PRIVACY_MODE,
    CONF_USE_HTTPS,
    DOMAIN,
)
from homeassistant.components.reolink.exceptions import ReolinkWebhookException
from homeassistant.components.reolink.host import DEFAULT_TIMEOUT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import (
    DHCP_FORMATTED_MAC,
    TEST_BC_PORT,
    TEST_HOST,
    TEST_HOST2,
    TEST_MAC,
    TEST_NVR_NAME,
    TEST_PASSWORD,
    TEST_PASSWORD2,
    TEST_PORT,
    TEST_PRIVACY,
    TEST_USE_HTTPS,
    TEST_USERNAME,
    TEST_USERNAME2,
)

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("reolink_connect")


async def test_config_flow_manual_success(
    hass: HomeAssistant, mock_setup_entry: MagicMock
) -> None:
    """Successful flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NVR_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: TEST_PORT,
        CONF_USE_HTTPS: TEST_USE_HTTPS,
        CONF_SUPPORTS_PRIVACY_MODE: TEST_PRIVACY,
        CONF_BC_PORT: TEST_BC_PORT,
    }
    assert result["options"] == {
        CONF_PROTOCOL: DEFAULT_PROTOCOL,
    }
    assert result["result"].unique_id == TEST_MAC


async def test_config_flow_privacy_success(
    hass: HomeAssistant, reolink_connect: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Successful flow when privacy mode is turned on."""
    reolink_connect.baichuan.privacy_mode.return_value = True
    reolink_connect.get_host_data.side_effect = LoginPrivacyModeError("Test error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "privacy"
    assert result["errors"] is None

    assert reolink_connect.baichuan.set_privacy_mode.call_count == 0
    reolink_connect.get_host_data.reset_mock(side_effect=True)

    with patch("homeassistant.components.reolink.config_flow.API_STARTUP_TIME", new=0):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert reolink_connect.baichuan.set_privacy_mode.call_count == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NVR_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: TEST_PORT,
        CONF_USE_HTTPS: TEST_USE_HTTPS,
        CONF_SUPPORTS_PRIVACY_MODE: TEST_PRIVACY,
        CONF_BC_PORT: TEST_BC_PORT,
    }
    assert result["options"] == {
        CONF_PROTOCOL: DEFAULT_PROTOCOL,
    }
    assert result["result"].unique_id == TEST_MAC

    reolink_connect.baichuan.privacy_mode.return_value = False


async def test_config_flow_errors(
    hass: HomeAssistant, reolink_connect: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Successful flow manually initialized by the user after some errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    reolink_connect.is_admin = False
    reolink_connect.user_level = "guest"
    reolink_connect.unsubscribe.side_effect = ReolinkError("Test error")
    reolink_connect.logout.side_effect = ReolinkError("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_USERNAME: "not_admin"}

    reolink_connect.is_admin = True
    reolink_connect.user_level = "admin"
    reolink_connect.get_host_data.side_effect = ReolinkError("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_HOST: "cannot_connect"}

    reolink_connect.get_host_data.side_effect = ReolinkWebhookException("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "webhook_exception"}

    reolink_connect.get_host_data.side_effect = json.JSONDecodeError(
        "test_error", "test", 1
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_HOST: "unknown"}

    reolink_connect.get_host_data.side_effect = CredentialsInvalidError("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}

    reolink_connect.get_host_data.side_effect = LoginFirmwareError("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "update_needed"}

    reolink_connect.valid_password.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_PASSWORD: "password_incompatible"}

    reolink_connect.valid_password.return_value = True
    reolink_connect.get_host_data.side_effect = ApiError("Test error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_HOST: "api_error"}

    reolink_connect.get_host_data.reset_mock(side_effect=True)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USE_HTTPS: TEST_USE_HTTPS,
            CONF_BC_PORT: TEST_BC_PORT,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NVR_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: TEST_PORT,
        CONF_USE_HTTPS: TEST_USE_HTTPS,
        CONF_SUPPORTS_PRIVACY_MODE: TEST_PRIVACY,
        CONF_BC_PORT: TEST_BC_PORT,
    }
    assert result["options"] == {
        CONF_PROTOCOL: DEFAULT_PROTOCOL,
    }

    reolink_connect.unsubscribe.reset_mock(side_effect=True)
    reolink_connect.logout.reset_mock(side_effect=True)


async def test_options_flow(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test specifying non default settings using options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            CONF_USE_HTTPS: TEST_USE_HTTPS,
            CONF_BC_PORT: TEST_BC_PORT,
        },
        options={
            CONF_PROTOCOL: "rtsp",
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_PROTOCOL: "rtmp"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_PROTOCOL: "rtmp",
    }


async def test_reauth(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test a reauth flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            CONF_USE_HTTPS: TEST_USE_HTTPS,
            CONF_BC_PORT: TEST_BC_PORT,
        },
        options={
            CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME2,
            CONF_PASSWORD: TEST_PASSWORD2,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_HOST] == TEST_HOST
    assert config_entry.data[CONF_USERNAME] == TEST_USERNAME2
    assert config_entry.data[CONF_PASSWORD] == TEST_PASSWORD2


async def test_reauth_abort_unique_id_mismatch(
    hass: HomeAssistant, mock_setup_entry: MagicMock, reolink_connect: MagicMock
) -> None:
    """Test a reauth flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            CONF_USE_HTTPS: TEST_USE_HTTPS,
            CONF_BC_PORT: TEST_BC_PORT,
        },
        options={
            CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    reolink_connect.mac_address = "aa:aa:aa:aa:aa:aa"

    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME2,
            CONF_PASSWORD: TEST_PASSWORD2,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert config_entry.data[CONF_HOST] == TEST_HOST
    assert config_entry.data[CONF_USERNAME] == TEST_USERNAME
    assert config_entry.data[CONF_PASSWORD] == TEST_PASSWORD

    reolink_connect.mac_address = TEST_MAC


async def test_dhcp_flow(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Successful flow from DHCP discovery."""
    dhcp_data = DhcpServiceInfo(
        ip=TEST_HOST,
        hostname="Reolink",
        macaddress=DHCP_FORMATTED_MAC,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=dhcp_data
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NVR_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: TEST_PORT,
        CONF_USE_HTTPS: TEST_USE_HTTPS,
        CONF_SUPPORTS_PRIVACY_MODE: TEST_PRIVACY,
        CONF_BC_PORT: TEST_BC_PORT,
    }
    assert result["options"] == {
        CONF_PROTOCOL: DEFAULT_PROTOCOL,
    }


async def test_dhcp_ip_update_aborted_if_wrong_mac(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    reolink_connect_class: MagicMock,
    reolink_connect: MagicMock,
) -> None:
    """Test dhcp discovery does not update the IP if the mac address does not match."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            CONF_USE_HTTPS: TEST_USE_HTTPS,
            CONF_BC_PORT: TEST_BC_PORT,
        },
        options={
            CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    # ensure the last_update_succes is False for the device_coordinator.
    reolink_connect.get_states.side_effect = ReolinkError("Test error")
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    dhcp_data = DhcpServiceInfo(
        ip=TEST_HOST2,
        hostname="Reolink",
        macaddress=DHCP_FORMATTED_MAC,
    )

    reolink_connect.mac_address = "aa:aa:aa:aa:aa:aa"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=dhcp_data
    )

    for host in (TEST_HOST, TEST_HOST2):
        expected_call = call(
            host,
            TEST_USERNAME,
            TEST_PASSWORD,
            port=TEST_PORT,
            use_https=TEST_USE_HTTPS,
            protocol=DEFAULT_PROTOCOL,
            timeout=DEFAULT_TIMEOUT,
            aiohttp_get_session_callback=ANY,
            bc_port=TEST_BC_PORT,
        )
        assert expected_call in reolink_connect_class.call_args_list

    for exc_call in reolink_connect_class.call_args_list:
        assert exc_call[0][0] in [TEST_HOST, TEST_HOST2]
        get_session = exc_call[1]["aiohttp_get_session_callback"]
        assert isinstance(get_session(), ClientSession)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    await hass.async_block_till_done()
    # Check that IP was not updated
    assert config_entry.data[CONF_HOST] == TEST_HOST

    reolink_connect.get_states.side_effect = None
    reolink_connect_class.reset_mock()
    reolink_connect.mac_address = TEST_MAC


@pytest.mark.parametrize(
    ("attr", "value", "expected", "host_call_list"),
    [
        (
            None,
            None,
            TEST_HOST2,
            [TEST_HOST, TEST_HOST2],
        ),
        (
            "get_state",
            AsyncMock(side_effect=ReolinkError("Test error")),
            TEST_HOST,
            [TEST_HOST, TEST_HOST2],
        ),
    ],
)
async def test_dhcp_ip_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    reolink_connect_class: MagicMock,
    reolink_connect: MagicMock,
    attr: str,
    value: Any,
    expected: str,
    host_call_list: list[str],
) -> None:
    """Test dhcp discovery aborts if already configured where the IP is updated if appropriate."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            CONF_USE_HTTPS: TEST_USE_HTTPS,
            CONF_BC_PORT: TEST_BC_PORT,
        },
        options={
            CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    # ensure the last_update_succes is False for the device_coordinator.
    reolink_connect.get_states.side_effect = ReolinkError("Test error")
    freezer.tick(DEVICE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    dhcp_data = DhcpServiceInfo(
        ip=TEST_HOST2,
        hostname="Reolink",
        macaddress=DHCP_FORMATTED_MAC,
    )

    if attr is not None:
        original = getattr(reolink_connect, attr)
        setattr(reolink_connect, attr, value)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=dhcp_data
    )

    for host in host_call_list:
        expected_call = call(
            host,
            TEST_USERNAME,
            TEST_PASSWORD,
            port=TEST_PORT,
            use_https=TEST_USE_HTTPS,
            protocol=DEFAULT_PROTOCOL,
            timeout=DEFAULT_TIMEOUT,
            aiohttp_get_session_callback=ANY,
            bc_port=TEST_BC_PORT,
        )
        assert expected_call in reolink_connect_class.call_args_list

    for exc_call in reolink_connect_class.call_args_list:
        assert exc_call[0][0] in host_call_list
        get_session = exc_call[1]["aiohttp_get_session_callback"]
        assert isinstance(get_session(), ClientSession)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    await hass.async_block_till_done()
    assert config_entry.data[CONF_HOST] == expected

    reolink_connect.get_states.side_effect = None
    reolink_connect_class.reset_mock()
    if attr is not None:
        setattr(reolink_connect, attr, original)


async def test_dhcp_ip_update_ingnored_if_still_connected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    reolink_connect_class: MagicMock,
    reolink_connect: MagicMock,
) -> None:
    """Test dhcp discovery is ignored when the camera is still properly connected to HA."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            CONF_USE_HTTPS: TEST_USE_HTTPS,
            CONF_BC_PORT: TEST_BC_PORT,
        },
        options={
            CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    dhcp_data = DhcpServiceInfo(
        ip=TEST_HOST2,
        hostname="Reolink",
        macaddress=DHCP_FORMATTED_MAC,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=dhcp_data
    )

    expected_call = call(
        TEST_HOST,
        TEST_USERNAME,
        TEST_PASSWORD,
        port=TEST_PORT,
        use_https=TEST_USE_HTTPS,
        protocol=DEFAULT_PROTOCOL,
        timeout=DEFAULT_TIMEOUT,
        aiohttp_get_session_callback=ANY,
        bc_port=TEST_BC_PORT,
    )
    assert expected_call in reolink_connect_class.call_args_list

    for exc_call in reolink_connect_class.call_args_list:
        assert exc_call[0][0] == TEST_HOST
        get_session = exc_call[1]["aiohttp_get_session_callback"]
        assert isinstance(get_session(), ClientSession)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    await hass.async_block_till_done()
    assert config_entry.data[CONF_HOST] == TEST_HOST

    reolink_connect.get_states.side_effect = None
    reolink_connect_class.reset_mock()


async def test_reconfig(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test a reconfiguration flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            CONF_USE_HTTPS: TEST_USE_HTTPS,
            CONF_BC_PORT: TEST_BC_PORT,
        },
        options={
            CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST2,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_HOST] == TEST_HOST2
    assert config_entry.data[CONF_USERNAME] == TEST_USERNAME
    assert config_entry.data[CONF_PASSWORD] == TEST_PASSWORD


async def test_reconfig_abort_unique_id_mismatch(
    hass: HomeAssistant, mock_setup_entry: MagicMock, reolink_connect: MagicMock
) -> None:
    """Test a reconfiguration flow aborts if the unique id does not match."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            CONF_USE_HTTPS: TEST_USE_HTTPS,
            CONF_BC_PORT: TEST_BC_PORT,
        },
        options={
            CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    reolink_connect.mac_address = "aa:aa:aa:aa:aa:aa"

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST2,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert config_entry.data[CONF_HOST] == TEST_HOST
    assert config_entry.data[CONF_USERNAME] == TEST_USERNAME
    assert config_entry.data[CONF_PASSWORD] == TEST_PASSWORD

    reolink_connect.mac_address = TEST_MAC
