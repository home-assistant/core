"""Tests for the Bitvis Power Hub config flow."""

import asyncio
from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, patch

from bitvis_protobuf.parse import PayloadSample
from bitvis_protobuf.powerhub_pb2 import Payload
import pytest

from homeassistant.components.bitvis.const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from homeassistant.components.bitvis.coordinator import async_get_listener_registry
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import (
    SECOND_DEVICE_MAC,
    TEST_DEVICE_MAC,
    FakeListener,
    patch_config_flow_connectivity,
)

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

ZEROCONF_HOST = "192.168.1.200"
USER_HOST = "192.168.1.100"


def _zeroconf_discovery(
    host: str = ZEROCONF_HOST,
    name: str = "Bitvis Power Hub._powerhub._udp.local.",
    port: int | None = DEFAULT_PORT,
) -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        hostname="powerhub.local.",
        name=name,
        port=port,
        properties={},
        type="_powerhub._udp.local.",
    )


ZEROCONF_DISCOVERY = _zeroconf_discovery()
UNRELATED_HOST = "10.9.9.9"


def _invalid_mac_datagram() -> bytes:
    payload = Payload()
    payload.sample.SetInParent()
    return payload.SerializeToString()


@pytest.mark.parametrize(
    ("input_host", "resolved_ip", "expected_host"),
    [
        pytest.param(USER_HOST, USER_HOST, USER_HOST, id="ipv4"),
        pytest.param("2001:db8::10", "2001:db8::10", "2001:db8::10", id="ipv6"),
        pytest.param(
            "my-powerhub.local", "10.0.0.5", "my-powerhub.local", id="hostname"
        ),
        pytest.param(
            "[2001:db8::10]", "2001:db8::10", "2001:db8::10", id="bracketed-ipv6"
        ),
    ],
)
async def test_user_form_create_entry(
    hass: HomeAssistant,
    input_host: str,
    resolved_ip: str,
    expected_host: str,
) -> None:
    """Test creating an entry via user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch_config_flow_connectivity(resolved_ip):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: input_host,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_HOST: expected_host,
        CONF_PORT: DEFAULT_PORT,
    }
    assert result["result"].unique_id == TEST_DEVICE_MAC


@pytest.mark.parametrize(
    ("connectivity_kwargs", "error_key"),
    [
        pytest.param(
            {"port_bind_side_effect": OSError("UDP port is unavailable")},
            "cannot_connect",
            id="cannot-connect",
        ),
        pytest.param({"invalid_mac": True}, "invalid_mac", id="invalid-mac"),
        pytest.param(
            {"deliver_mac": False, "discovery_timeout": True},
            "timeout_connect",
            id="timeout",
        ),
    ],
)
async def test_user_form_error_and_recovery(
    hass: HomeAssistant,
    connectivity_kwargs: dict[str, object],
    error_key: str,
) -> None:
    """Test user form error then successful recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch_config_flow_connectivity(USER_HOST, **connectivity_kwargs):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: USER_HOST,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    with patch_config_flow_connectivity(USER_HOST):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: USER_HOST,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_HOST: USER_HOST,
        CONF_PORT: DEFAULT_PORT,
    }
    assert result["result"].unique_id == TEST_DEVICE_MAC


@pytest.mark.parametrize(
    "input_host",
    [
        pytest.param(USER_HOST, id="same-host"),
        pytest.param("192.168.1.101", id="different-host"),
    ],
)
async def test_user_form_duplicate_mac(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, input_host: str
) -> None:
    """Test duplicate detection is based on MAC address, not host."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch_config_flow_connectivity(input_host):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: input_host,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_form_reused_ip_new_device(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a new device can be added at an IP already stored on another entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch_config_flow_connectivity(USER_HOST, mac_address=SECOND_DEVICE_MAC):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: USER_HOST,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: USER_HOST,
        CONF_PORT: DEFAULT_PORT,
    }
    assert result["result"].unique_id == SECOND_DEVICE_MAC


@pytest.mark.parametrize(
    ("connectivity_kwargs", "reason"),
    [
        pytest.param(
            {"port_bind_side_effect": OSError("UDP port is unavailable")},
            "cannot_connect",
            id="cannot-connect",
        ),
        pytest.param({"invalid_mac": True}, "invalid_mac", id="invalid-mac"),
        pytest.param(
            {"deliver_mac": False, "discovery_timeout": True},
            "timeout_connect",
            id="timeout",
        ),
    ],
)
async def test_zeroconf_abort(
    hass: HomeAssistant,
    connectivity_kwargs: dict[str, object],
    reason: str,
) -> None:
    """Test zeroconf discovery abort reasons."""
    with patch_config_flow_connectivity(ZEROCONF_HOST, **connectivity_kwargs):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_zeroconf_duplicate(
    hass: HomeAssistant, mock_zeroconf_config_entry: MockConfigEntry
) -> None:
    """Test that a duplicate zeroconf discovery is aborted by MAC address."""
    mock_zeroconf_config_entry.add_to_hass(hass)

    with patch_config_flow_connectivity(ZEROCONF_HOST):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_reused_ip_new_device(
    hass: HomeAssistant, mock_zeroconf_config_entry: MockConfigEntry
) -> None:
    """Test zeroconf can add a new device at an IP already stored on another entry."""
    mock_zeroconf_config_entry.add_to_hass(hass)

    with patch_config_flow_connectivity(ZEROCONF_HOST, mac_address=SECOND_DEVICE_MAC):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: ZEROCONF_HOST,
        CONF_PORT: DEFAULT_PORT,
    }
    assert result["result"].unique_id == SECOND_DEVICE_MAC


@pytest.mark.parametrize(
    ("name", "port", "expected_title"),
    [
        pytest.param(
            "Bitvis Power Hub._powerhub._udp.local.",
            DEFAULT_PORT,
            "Bitvis Power Hub",
            id="happy-path",
        ),
        pytest.param(
            "Bitvis Power Hub._powerhub._udp.local.",
            None,
            "Bitvis Power Hub",
            id="none-port",
        ),
        pytest.param(
            "My Custom Hub._powerhub._udp.local.",
            DEFAULT_PORT,
            "My Custom Hub",
            id="friendly-name",
        ),
        pytest.param("", DEFAULT_PORT, DEFAULT_NAME, id="empty-name"),
        pytest.param(
            "._powerhub._udp.local.", DEFAULT_PORT, DEFAULT_NAME, id="dot-prefixed"
        ),
    ],
)
async def test_zeroconf_create_entry(
    hass: HomeAssistant,
    name: str,
    port: int | None,
    expected_title: str,
) -> None:
    """Test zeroconf confirm creates an entry with title, data, and unique_id."""
    discovery = _zeroconf_discovery(name=name, port=port)

    with patch_config_flow_connectivity(ZEROCONF_HOST):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=discovery,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["data"] == {
        CONF_HOST: ZEROCONF_HOST,
        CONF_PORT: DEFAULT_PORT,
    }
    assert result["result"].unique_id == TEST_DEVICE_MAC


async def test_zeroconf_updates_host_on_new_ip(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test rediscovery on a new IP updates the stored host and aborts."""
    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data[CONF_HOST] != ZEROCONF_HOST

    with patch_config_flow_connectivity(ZEROCONF_HOST):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == ZEROCONF_HOST


async def test_aborted_flow_removes_listener(
    hass: HomeAssistant,
    mock_shared_listener: FakeListener,
) -> None:
    """Test listener is stopped after an aborted config flow."""
    with patch_config_flow_connectivity(
        USER_HOST,
        deliver_mac=False,
        discovery_timeout=True,
        shared_listener=mock_shared_listener,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: USER_HOST,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "timeout_connect"}
    mock_shared_listener.stop.assert_awaited_once()
    assert not async_get_listener_registry(hass).has_listener(DEFAULT_PORT)


async def test_invalid_mac_from_other_host_is_ignored(
    hass: HomeAssistant, mock_shared_listener: FakeListener
) -> None:
    """Test an invalid-MAC datagram from another host does not fail the flow."""
    with patch_config_flow_connectivity(
        USER_HOST, deliver_mac=False, shared_listener=mock_shared_listener
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        configure_task = asyncio.create_task(
            hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: USER_HOST,
                },
            )
        )
        await hass.async_block_till_done()

        mock_shared_listener.dispatch(_invalid_mac_datagram(), (UNRELATED_HOST, 1234))
        mock_shared_listener.deliver(
            PayloadSample(mac_address=TEST_DEVICE_MAC, sample=MagicMock()),
            (USER_HOST, 1234),
        )
        result = await configure_task

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_DEVICE_MAC


async def test_invalid_mac_does_not_fail_other_flow(
    hass: HomeAssistant, mock_shared_listener: FakeListener
) -> None:
    """Test an invalid-MAC datagram only fails the flow waiting for that host."""

    async def resolve_host(host: str) -> set[str]:
        return {host}

    with (
        patch(
            "homeassistant.components.bitvis.config_flow.async_verify_udp_port_bindable",
            new_callable=AsyncMock,
        ),
        patch(
            "homeassistant.components.bitvis.config_flow.async_resolve_host",
            side_effect=resolve_host,
        ),
        patch(
            "homeassistant.components.bitvis.coordinator.SharedListener",
            return_value=mock_shared_listener,
        ),
    ):
        first_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        first_task = asyncio.create_task(
            hass.config_entries.flow.async_configure(
                first_result["flow_id"],
                {
                    CONF_HOST: USER_HOST,
                },
            )
        )
        await hass.async_block_till_done()

        second_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        second_task = asyncio.create_task(
            hass.config_entries.flow.async_configure(
                second_result["flow_id"],
                {
                    CONF_HOST: ZEROCONF_HOST,
                },
            )
        )
        await hass.async_block_till_done()

        mock_shared_listener.dispatch(_invalid_mac_datagram(), (ZEROCONF_HOST, 1234))
        mock_shared_listener.deliver(
            PayloadSample(mac_address=TEST_DEVICE_MAC, sample=MagicMock()),
            (USER_HOST, 1234),
        )
        first_result = await first_task
        second_result = await second_task

    assert first_result["type"] is FlowResultType.CREATE_ENTRY
    assert first_result["result"].unique_id == TEST_DEVICE_MAC
    assert second_result["type"] is FlowResultType.FORM
    assert second_result["errors"] == {"base": "invalid_mac"}


async def test_concurrent_flow_same_host_aborts(hass: HomeAssistant) -> None:
    """Test concurrent flows for the same host abort with already_in_progress."""
    with patch_config_flow_connectivity(USER_HOST, deliver_mac=False):
        first_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        first_task = asyncio.create_task(
            hass.config_entries.flow.async_configure(
                first_result["flow_id"],
                {
                    CONF_HOST: USER_HOST,
                },
            )
        )
        await hass.async_block_till_done()

        second_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        second_result = await hass.config_entries.flow.async_configure(
            second_result["flow_id"],
            {
                CONF_HOST: USER_HOST,
            },
        )

        first_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first_task

    assert second_result["type"] is FlowResultType.ABORT
    assert second_result["reason"] == "already_in_progress"


async def test_discovery_register_runtime_error_aborts(hass: HomeAssistant) -> None:
    """Test discovery aborts when filter registration raises RuntimeError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch_config_flow_connectivity(
        USER_HOST,
        deliver_mac=False,
        register_side_effect=RuntimeError("Filter already registered"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: USER_HOST,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_zeroconf_concurrent_flow_same_host_aborts(hass: HomeAssistant) -> None:
    """Test concurrent zeroconf flows for the same host abort."""
    with patch_config_flow_connectivity(ZEROCONF_HOST, deliver_mac=False):
        first_task = asyncio.create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_ZEROCONF},
                data=ZEROCONF_DISCOVERY,
            )
        )
        await hass.async_block_till_done()

        second_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data=ZEROCONF_DISCOVERY,
        )

        first_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first_task

    assert second_result["type"] is FlowResultType.ABORT
    assert second_result["reason"] == "already_in_progress"


@pytest.mark.parametrize(
    ("listener_already_running", "expected_awaits"),
    [
        pytest.param(True, 0, id="listener-exists"),
        pytest.param(False, 1, id="no-listener"),
    ],
)
async def test_user_form_port_bind_check(
    hass: HomeAssistant,
    mock_shared_listener: FakeListener,
    listener_already_running: bool,
    expected_awaits: int,
) -> None:
    """Test user flow skips the port bind check only when a listener exists."""
    if listener_already_running:
        with patch(
            "homeassistant.components.bitvis.coordinator.SharedListener",
            return_value=mock_shared_listener,
        ):
            await async_get_listener_registry(hass).async_get_or_create(DEFAULT_PORT)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    kwargs: dict[str, object] = {
        "mac_address": SECOND_DEVICE_MAC
        if listener_already_running
        else TEST_DEVICE_MAC
    }
    if listener_already_running:
        kwargs["shared_listener"] = mock_shared_listener

    with patch_config_flow_connectivity("192.168.1.101", **kwargs) as mock_verify:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.101",
            },
        )

    assert mock_verify.await_count == expected_awaits
    assert result["type"] is FlowResultType.CREATE_ENTRY
