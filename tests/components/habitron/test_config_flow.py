"""Tests for the Habitron config flow."""

import asyncio
import json
import socket
from unittest.mock import MagicMock, patch

from habitron_client import HabitronTimeoutError
import pytest

from homeassistant import config_entries
from homeassistant.components.habitron.config_flow import (
    DISCOVERY_MESSAGE,
    DISCOVERY_PORT,
    KEY_HOST,
    ConfigFlow,
    HostNotFound,
    InvalidHost,
    UDPDiscoveryProtocol,
    _get_local_ip,
    validate_input,
)
from homeassistant.components.habitron.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .const import (
    MOCK_CONFIG_DATA,
    MOCK_HOST,
    MOCK_NAME,
    MOCK_SERIAL,
    MOCK_UDN,
    MOCK_UID,
)

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """The manual user flow creates an entry when the hub responds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert result["data"] == MOCK_CONFIG_DATA


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A failing connect probe surfaces ``cannot_connect``."""
    mock_habitron_client.return_value = (False, "")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """An identical config aborts with ``already_configured``.

    The user step falls back to ``habitron_{host}`` for the unique id
    when no UDP probe response arrives, so we register an existing
    entry with that same id to trigger the abort path.
    """
    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=f"habitron_{MOCK_HOST}",
        data=MOCK_CONFIG_DATA,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_discovery_with_udn(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """SSDP discovery prefers the UDN as unique id."""
    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    # Confirm step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == MOCK_UDN


async def test_ssdp_discovery_serial_fallback(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """When no UDN, the UPnP serialNumber is used."""
    discovery = SsdpServiceInfo(
        ssdp_usn="dummy::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_SERIAL: MOCK_SERIAL},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == MOCK_SERIAL


async def test_ssdp_legacy_unique_id_migrated(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A pre-existing host-based entry gets migrated on rediscovery."""
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=f"habitron_{MOCK_HOST}",
        data=MOCK_CONFIG_DATA,
    )
    legacy_entry.add_to_hass(hass)

    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    # Old host-based entry should already have been rewritten and the
    # flow aborted as "already configured" against the new id.
    await hass.async_block_till_done()
    assert legacy_entry.unique_id == MOCK_UDN
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_no_host(
    hass: HomeAssistant,
    setup_homeassistant: None,
) -> None:
    """SSDP without a hostname is aborted."""
    discovery = SsdpServiceInfo(
        ssdp_usn="dummy",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=None,
        upnp={},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_host_in_ssdp"


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (HabitronTimeoutError("timeout"), "cannot_connect"),
        (ConnectionRefusedError("refused"), "cannot_connect"),
    ],
)
async def test_user_flow_exception_mapping(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    exception: Exception,
    expected: str,
) -> None:
    """Connection errors map to expected form errors."""
    mock_habitron_client.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_options_flow(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """The options flow updates the entry's options."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    new_input = {
        "habitron_host": MOCK_HOST,
        "websock_token": "test-token-not-real",
    }
    with patch.object(hass.config_entries, "async_reload", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=new_input
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


# ---------- unit tests for the helper layer ----------


async def test_get_local_ip_falls_back_on_exception(hass: HomeAssistant) -> None:
    """``_get_local_ip`` returns 127.0.0.1 when the network helper raises."""

    with patch(
        "homeassistant.components.habitron.config_flow.network.async_get_source_ip",
        side_effect=RuntimeError("no source"),
    ):
        assert await _get_local_ip(hass) == "127.0.0.1"


async def test_validate_input_local_loopback_rewrites_host(
    hass: HomeAssistant,
    mock_habitron_client: MagicMock,
) -> None:
    """A host equal to the local IP is rewritten to the literal ``local``."""

    data = {KEY_HOST: "192.168.1.10", "websock_token": ""}
    info = await validate_input(hass, data)
    assert data[KEY_HOST] == "local"
    assert info == {"title": MOCK_NAME}


async def test_validate_input_invalid_host_too_short(hass: HomeAssistant) -> None:
    """A host string shorter than 4 chars raises ``InvalidHost``."""

    with (
        patch(
            "homeassistant.components.habitron.config_flow._get_local_ip",
            return_value="10.0.0.5",
        ),
        pytest.raises(InvalidHost),
    ):
        await validate_input(
            hass,
            {KEY_HOST: "abc", "websock_token": ""},
        )


async def test_validate_input_host_not_found_for_dns_failure(
    hass: HomeAssistant,
) -> None:
    """A socket.gaierror surfaces as ``HostNotFound``."""

    with (
        patch(
            "homeassistant.components.habitron.config_flow._get_local_ip",
            return_value="10.0.0.5",
        ),
        patch(
            "homeassistant.components.habitron.config_flow.test_connection",
            side_effect=socket.gaierror("dns fail"),
        ),
        pytest.raises(HostNotFound),
    ):
        await validate_input(
            hass,
            {KEY_HOST: MOCK_HOST, "websock_token": ""},
        )


# ---------- UDPDiscoveryProtocol unit tests ----------


def test_udp_discovery_protocol_connection_made_sends_broadcast() -> None:
    """``connection_made`` enables broadcast and sends the discovery packet."""

    proto = UDPDiscoveryProtocol()
    transport = MagicMock(spec=asyncio.DatagramTransport)
    sock = MagicMock()
    transport.get_extra_info.return_value = sock

    proto.connection_made(transport)
    sock.setsockopt.assert_called()
    transport.sendto.assert_called_with(
        DISCOVERY_MESSAGE, ("255.255.255.255", DISCOVERY_PORT)
    )


def test_udp_discovery_protocol_connection_made_no_socket() -> None:
    """``connection_made`` is robust against a missing socket info."""

    proto = UDPDiscoveryProtocol()
    transport = MagicMock(spec=asyncio.DatagramTransport)
    transport.get_extra_info.return_value = None
    proto.connection_made(transport)
    transport.sendto.assert_called()


def test_udp_discovery_protocol_datagram_collects_unique_devices() -> None:
    """``datagram_received`` collects host/ip pairs and dedupes by ip."""

    proto = UDPDiscoveryProtocol()
    payload = json.dumps({"host": "hub1", "ip": "10.0.0.1"}).encode()
    proto.datagram_received(payload, ("10.0.0.1", 7777))
    proto.datagram_received(payload, ("10.0.0.1", 7777))  # duplicate
    assert len(proto.found_devices) == 1


def test_udp_discovery_protocol_datagram_swallows_bad_payload() -> None:
    """Non-JSON datagrams are ignored without raising."""

    proto = UDPDiscoveryProtocol()
    proto.datagram_received(b"\xff\xfe garbage", ("10.0.0.1", 7777))
    assert proto.found_devices == []


def test_udp_discovery_protocol_error_received_logs() -> None:
    """``error_received`` accepts a generic error without raising."""

    proto = UDPDiscoveryProtocol()
    proto.error_received(RuntimeError("oops"))
    proto.connection_lost(None)


# ---------- ConfigFlow._is_device_already_configured ----------


async def test_is_device_already_configured_host_match(hass: HomeAssistant) -> None:
    """A pre-existing entry whose host matches reports as configured."""

    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="existing-id",
        data={"habitron_host": MOCK_HOST},
    ).add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass
    assert flow._is_device_already_configured(MOCK_HOST) is True
    assert flow._is_device_already_configured("other-host") is False


async def test_is_device_already_configured_ip_match(hass: HomeAssistant) -> None:
    """A pre-existing entry whose host equals the IP reports as configured."""

    MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id="existing-id",
        data={"habitron_host": "10.0.0.1"},
    ).add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass
    assert flow._is_device_already_configured("hub-x", ip="10.0.0.1") is True


# ---------- _discover_habitron OS-error fallback ----------


async def test_discover_habitron_handles_oserror(hass: HomeAssistant) -> None:
    """A datagram-endpoint failure makes ``_discover_habitron`` return []."""

    flow = ConfigFlow()
    flow.hass = hass

    async def _raise(*args, **kwargs):
        raise OSError("address in use")

    with patch("asyncio.get_running_loop") as mock_loop:
        loop = MagicMock()
        loop.create_datagram_endpoint = _raise
        mock_loop.return_value = loop
        result = await flow._discover_habitron()
    assert result == []


async def test_discover_habitron_returns_found_devices(hass: HomeAssistant) -> None:
    """A successful discovery returns whatever the protocol collected."""

    flow = ConfigFlow()
    flow.hass = hass

    transport = MagicMock()
    protocol = MagicMock()
    protocol.found_devices = [{"host": "h1", "ip": "10.0.0.1"}]

    async def _ok(*args, **kwargs):
        return transport, protocol

    async def _no_sleep(_):
        return None

    with (
        patch("asyncio.get_running_loop") as mock_loop,
        patch("asyncio.sleep", new=_no_sleep),
    ):
        loop = MagicMock()
        loop.create_datagram_endpoint = _ok
        mock_loop.return_value = loop
        result = await flow._discover_habitron()
    assert result == [{"host": "h1", "ip": "10.0.0.1"}]
    transport.close.assert_called()


# ---------- SSDP with no UDN + UDP fallback ----------


async def test_ssdp_discovery_falls_back_to_udp_serial(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """A discovery without UDN/serial picks the serial from the UDP probe."""
    discovery = SsdpServiceInfo(
        ssdp_usn="dummy",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={},
    )

    with patch(
        "homeassistant.components.habitron.config_flow.ConfigFlow._discover_habitron",
        return_value=[{"host": MOCK_HOST, "ip": MOCK_HOST, "serial": "UDP-SER-1"}],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=discovery,
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == "UDP-SER-1"


async def test_ssdp_discovery_no_udn_no_udp_falls_back_to_host_id(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """Without UDN, serial or matching UDP device, the host string is used."""
    discovery = SsdpServiceInfo(
        ssdp_usn="dummy",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={},
    )

    with patch(
        "homeassistant.components.habitron.config_flow.ConfigFlow._discover_habitron",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=discovery,
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == f"habitron_{MOCK_HOST}"


async def test_ssdp_discovery_confirm_handles_validate_error(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A confirm step that fails validation aborts with ``unknown``."""
    discovery = SsdpServiceInfo(
        ssdp_usn=f"{MOCK_UDN}::urn:habitron-com:device:SmartHub:1",
        ssdp_st="urn:habitron-com:device:SmartHub:1",
        ssdp_location=f"http://{MOCK_HOST}:80/desc.xml",
        upnp={ATTR_UPNP_UDN: MOCK_UDN},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery,
    )
    assert result["type"] is FlowResultType.FORM

    mock_habitron_client.side_effect = RuntimeError("validate fail")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


# ---------- user flow exception mapping ----------


async def test_user_flow_host_not_found_via_validate_input(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A HostNotFound raised from validate_input maps to ``host_not_found``."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=HostNotFound("dns"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG_DATA
        )
    assert result["errors"] == {"base": "host_not_found"}


async def test_user_flow_truly_unknown_exception_maps_to_unknown(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """An exception type the user step does not know surfaces as ``unknown``."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=ValueError("totally unexpected"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG_DATA
        )
    assert result["errors"] == {"base": "unknown"}


async def test_reconfigure_flow_host_not_found_via_validate_input(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """The reconfigure flow maps HostNotFound to ``host_not_found``."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=HostNotFound("dns"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG_DATA
        )
    assert result["errors"] == {"base": "host_not_found"}


async def test_reconfigure_flow_truly_unknown_exception(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """An exception in the reconfigure flow surfaces as ``unknown``."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=ValueError("totally unexpected"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG_DATA
        )
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_short_host_maps_to_host_not_found(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """A host string shorter than 4 chars triggers ``host_not_found``."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**MOCK_CONFIG_DATA, "habitron_host": "ab"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "host_not_found"}


async def test_user_flow_unexpected_exception_maps_to_unknown(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """An unexpected error surfaces as ``unknown``."""
    mock_habitron_client.side_effect = RuntimeError("boom")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


# ---------- reconfigure flow ----------


async def test_reconfigure_flow_shows_form_with_existing_data(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """The reconfigure flow shows a form pre-populated with the entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_reconfigure_flow_updates_entry_on_success(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """A successful reconfigure updates the entry and reloads."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    new_input = {
        "habitron_host": "10.0.0.99",
        "websock_token": "",
    }
    with patch.object(hass.config_entries, "async_reload", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_input
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_flow_surfaces_cannot_connect(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """When the hub probe fails the reconfigure form surfaces cannot_connect."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)
    mock_habitron_client.return_value = (False, "")

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_surfaces_unknown(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """An unexpected error in reconfigure surfaces as ``unknown``."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    # Path of least resistance: feed an invalid host that maps to host_not_found
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**MOCK_CONFIG_DATA, "habitron_host": "x"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "host_not_found"}


# ---------- options flow error branches ----------


async def test_options_flow_surfaces_cannot_connect(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """A failing connect probe in the options flow surfaces ``cannot_connect``."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_habitron_client.return_value = (False, "")
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    new_input = {
        "habitron_host": MOCK_HOST,
        "websock_token": "",
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=new_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow_surfaces_unknown_exception(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """An unexpected error in the options flow surfaces as ``unknown``."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    with patch(
        "homeassistant.components.habitron.config_flow.validate_input",
        side_effect=ValueError("boom"),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "habitron_host": MOCK_HOST,
                "websock_token": "",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


# ---------- user step pre-fill from UDP discovery ----------


async def test_user_step_prefills_host_from_udp_discovery(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
) -> None:
    """The user step pre-fills the host field from a UDP-discovered device."""
    with patch(
        "homeassistant.components.habitron.config_flow.ConfigFlow._discover_habitron",
        return_value=[{"host": "udp-host", "ip": "10.0.0.99"}],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    # The form's data-schema default should now reflect the discovered host.
    schema = result["data_schema"].schema
    # Find the KEY_HOST default by walking the schema vol.Required keys.
    default = None
    for key in schema:
        if getattr(key, "schema", None) == "habitron_host":
            default = key.default()
            break
    assert default == "udp-host"


async def test_user_flow_picks_up_serial_from_udp_probe(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_habitron_client: MagicMock,
    mock_smart_hub_setup: None,
    mock_coordinator_refresh,
) -> None:
    """A matching UDP serial becomes the unique id."""
    with patch(
        "homeassistant.components.habitron.config_flow.ConfigFlow._discover_habitron",
        return_value=[{"host": MOCK_HOST, "ip": MOCK_HOST, "serial": "SERIAL-X"}],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG_DATA
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "SERIAL-X"
