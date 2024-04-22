"""Test the Reolink config flow."""

from datetime import timedelta
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from reolink_aio.exceptions import ApiError, CredentialsInvalidError, ReolinkError

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.reolink import DEVICE_UPDATE_INTERVAL, const
from homeassistant.components.reolink.config_flow import DEFAULT_PROTOCOL
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
from homeassistant.util.dt import utcnow

from .conftest import (
    DHCP_FORMATTED_MAC,
    TEST_HOST,
    TEST_HOST2,
    TEST_MAC,
    TEST_NVR_NAME,
    TEST_PASSWORD,
    TEST_PASSWORD2,
    TEST_PORT,
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
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
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
        const.CONF_USE_HTTPS: TEST_USE_HTTPS,
    }
    assert result["options"] == {
        CONF_PROTOCOL: DEFAULT_PROTOCOL,
    }


async def test_config_flow_errors(
    hass: HomeAssistant, reolink_connect: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Successful flow manually initialized by the user after some errors."""
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    reolink_connect.is_admin = False
    reolink_connect.user_level = "guest"
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
    assert result["errors"] == {CONF_HOST: "invalid_auth"}

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

    reolink_connect.get_host_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            const.CONF_USE_HTTPS: TEST_USE_HTTPS,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NVR_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_PORT: TEST_PORT,
        const.CONF_USE_HTTPS: TEST_USE_HTTPS,
    }
    assert result["options"] == {
        CONF_PROTOCOL: DEFAULT_PROTOCOL,
    }


async def test_options_flow(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test specifying non default settings using options flow."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            const.CONF_USE_HTTPS: TEST_USE_HTTPS,
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


async def test_change_connection_settings(
    hass: HomeAssistant, mock_setup_entry: MagicMock
) -> None:
    """Test changing connection settings by issuing a second user config flow."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            const.CONF_USE_HTTPS: TEST_USE_HTTPS,
        },
        options={
            CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST2,
            CONF_USERNAME: TEST_USERNAME2,
            CONF_PASSWORD: TEST_PASSWORD2,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == TEST_HOST2
    assert config_entry.data[CONF_USERNAME] == TEST_USERNAME2
    assert config_entry.data[CONF_PASSWORD] == TEST_PASSWORD2


async def test_reauth(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test a reauth flow."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            const.CONF_USE_HTTPS: TEST_USE_HTTPS,
        },
        options={
            CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
            "title_placeholders": {"name": TEST_NVR_NAME},
            "unique_id": format_mac(TEST_MAC),
        },
        data=config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

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


async def test_dhcp_flow(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Successful flow from DHCP discovery."""
    dhcp_data = dhcp.DhcpServiceInfo(
        ip=TEST_HOST,
        hostname="Reolink",
        macaddress=DHCP_FORMATTED_MAC,
    )

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=dhcp_data
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
        const.CONF_USE_HTTPS: TEST_USE_HTTPS,
    }
    assert result["options"] == {
        CONF_PROTOCOL: DEFAULT_PROTOCOL,
    }


@pytest.mark.parametrize(
    ("last_update_success", "attr", "value", "expected", "host_call_list"),
    [
        (
            False,
            None,
            None,
            TEST_HOST2,
            [TEST_HOST, TEST_HOST2, TEST_HOST2],
        ),
        (
            True,
            None,
            None,
            TEST_HOST,
            [TEST_HOST],
        ),
        (
            False,
            "get_state",
            AsyncMock(side_effect=ReolinkError("Test error")),
            TEST_HOST,
            [TEST_HOST, TEST_HOST2],
        ),
        (
            False,
            "mac_address",
            "aa:aa:aa:aa:aa:aa",
            TEST_HOST,
            [TEST_HOST, TEST_HOST2],
        ),
    ],
)
async def test_dhcp_ip_update(
    hass: HomeAssistant,
    reolink_connect_class: MagicMock,
    reolink_connect: MagicMock,
    last_update_success: bool,
    attr: str,
    value: Any,
    expected: str,
    host_call_list: list[str],
) -> None:
    """Test dhcp discovery aborts if already configured where the IP is updated if appropriate."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            const.CONF_USE_HTTPS: TEST_USE_HTTPS,
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

    if not last_update_success:
        # ensure the last_update_succes is False for the device_coordinator.
        reolink_connect.get_states = AsyncMock(side_effect=ReolinkError("Test error"))
        async_fire_time_changed(
            hass, utcnow() + DEVICE_UPDATE_INTERVAL + timedelta(minutes=1)
        )
        await hass.async_block_till_done()

    dhcp_data = dhcp.DhcpServiceInfo(
        ip=TEST_HOST2,
        hostname="Reolink",
        macaddress=DHCP_FORMATTED_MAC,
    )

    if attr is not None:
        setattr(reolink_connect, attr, value)

    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=dhcp_data
    )

    expected_calls = [
        call(
            host,
            TEST_USERNAME,
            TEST_PASSWORD,
            port=TEST_PORT,
            use_https=TEST_USE_HTTPS,
            protocol=DEFAULT_PROTOCOL,
            timeout=DEFAULT_TIMEOUT,
        )
        for host in host_call_list
    ]

    assert reolink_connect_class.call_args_list == expected_calls

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    await hass.async_block_till_done()
    assert config_entry.data[CONF_HOST] == expected
