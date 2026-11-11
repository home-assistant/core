"""Tests for Gree discovery and per-device enrollment."""

import asyncio
from ipaddress import IPv4Address
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from greeclimate.device import DeviceInfo
from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.gree.const import CONF_IDENTIFIER, DOMAIN
from homeassistant.components.gree.discovery import (
    async_get_discovery,
    device_info_to_data,
    normalize_identifier,
)
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import discovery_flow, entity_registry as er
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.setup import async_setup_component

from .common import FakeDiscovery, build_device_mock

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "discovery_entry")

DHCP_SERVICE_INFO = DhcpServiceInfo(
    hostname="gree",
    ip="192.0.2.10",
    macaddress="0447caaabbcc",
)


async def start_dhcp_flow(
    hass: HomeAssistant, service_info: DhcpServiceInfo = DHCP_SERVICE_INFO
) -> config_entries.ConfigFlowResult:
    """Start the public DHCP config flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=service_info,
    )


def block_discovery_scan(
    discovery: MagicMock, scan_started: asyncio.Event, release_scan: asyncio.Event
) -> None:
    """Hold one fake discovery scan open for a deterministic race."""
    create_discovery = discovery.side_effect

    def create_blocked_discovery(timeout: int) -> FakeDiscovery:
        scanner = create_discovery(timeout)

        async def wait_for_scan(
            wait_for: int = 0,
            *,
            target_addresses: list[IPv4Address] | None = None,
        ) -> list[DeviceInfo]:
            scan_started.set()
            await release_scan.wait()
            return await scanner._async_scan(
                wait_for, target_addresses=target_addresses
            )

        scanner.scan.side_effect = wait_for_scan
        return scanner

    discovery.side_effect = create_blocked_discovery


def add_entry(
    hass: HomeAssistant,
    data: dict[str, Any],
    *,
    source: str = config_entries.SOURCE_USER,
    state: ConfigEntryState = ConfigEntryState.NOT_LOADED,
    disabled_by: ConfigEntryDisabler | None = None,
) -> MockConfigEntry:
    """Add an existing device entry without starting a connection."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=1,
        unique_id=normalize_identifier(data[CONF_IDENTIFIER]),
        title="User chosen title",
        data=data,
        source=source,
        state=state,
        disabled_by=disabled_by,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize(
    "disabled_by",
    [
        pytest.param(None, id="enabled"),
        pytest.param(ConfigEntryDisabler.USER, id="disabled"),
    ],
)
async def test_user_shows_candidates(
    hass: HomeAssistant,
    device: MagicMock,
    discovery_entry: MockConfigEntry,
    disabled_by: ConfigEntryDisabler | None,
) -> None:
    """An existing non-ignored owner is preserved during manual device setup."""
    await hass.config_entries.async_set_disabled_by(
        discovery_entry.entry_id, disabled_by
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_device"
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry]
    assert discovery_entry.disabled_by is disabled_by
    device().bind.assert_not_awaited()


async def test_initial_user_add_persists_discovery_without_devices(
    hass: HomeAssistant,
    discovery_entry: MockConfigEntry,
    discovery: MagicMock,
    device: MagicMock,
) -> None:
    """Initial setup creates a discovery owner only after explicit confirmation."""
    discovery.mock_devices.clear()
    await hass.config_entries.async_remove(discovery_entry.entry_id)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_discovery"
    assert not hass.config_entries.async_entries(DOMAIN)
    device().bind.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN
    assert result["result"].version == 2
    assert result["result"].minor_version == 1
    assert result["data"] == {}
    assert hass.config_entries.async_entries(DOMAIN) == [result["result"]]
    device().bind.assert_not_awaited()


async def test_dhcp_match_requires_confirmation_for_discovery_owner(
    hass: HomeAssistant,
    discovery_entry: MockConfigEntry,
    discovery: MagicMock,
    device: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A verified DHCP device offers only the persistent discovery owner."""
    await hass.config_entries.async_remove(discovery_entry.entry_id)
    discovery.mock_devices = [
        build_device_mock(
            name="Gree unit",
            ipAddress=DHCP_SERVICE_INFO.ip,
            identifier="04:47:CA:AA:BB:CC",
        )
    ]

    result = await start_dhcp_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_discovery"
    assert not hass.config_entries.async_entries(DOMAIN)
    assert not entity_registry.entities
    device.return_value.bind.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN
    assert result["result"].data == {}
    assert result["result"].source == config_entries.SOURCE_DHCP
    assert hass.config_entries.async_entries(DOMAIN) == [result["result"]]
    assert not entity_registry.entities
    device.return_value.bind.assert_not_awaited()


@pytest.mark.parametrize(
    "responders",
    [
        pytest.param([], id="no-responders"),
        pytest.param([("04:47:CA:AA:BB:CD", DHCP_SERVICE_INFO.ip)], id="wrong-mac"),
        pytest.param([("04:47:CA:AA:BB:CC", "192.0.2.11")], id="wrong-ip"),
    ],
)
async def test_dhcp_requires_matching_mac_and_ip(
    hass: HomeAssistant,
    discovery_entry: MockConfigEntry,
    discovery: MagicMock,
    device: MagicMock,
    responders: list[tuple[str, str]],
) -> None:
    """A vendor prefix alone cannot suggest an unverified device."""
    await hass.config_entries.async_remove(discovery_entry.entry_id)
    discovery.mock_devices = [
        build_device_mock(ipAddress=ip, identifier=mac) for mac, ip in responders
    ]

    result = await start_dhcp_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    assert not hass.config_entries.async_entries(DOMAIN)
    device.return_value.bind.assert_not_awaited()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(OSError("network down"), id="network-error"),
        pytest.param(TimeoutError("scan timed out"), id="timeout"),
    ],
)
async def test_dhcp_scan_error_aborts_without_enrollment(
    hass: HomeAssistant,
    discovery_entry: MockConfigEntry,
    discovery: MagicMock,
    device: MagicMock,
    error: Exception,
) -> None:
    """Scanner failures do not become device suggestions."""
    await hass.config_entries.async_remove(discovery_entry.entry_id)
    create_discovery = discovery.side_effect

    def create_failing_discovery(timeout: int) -> FakeDiscovery:
        scanner = create_discovery(timeout)
        scanner.scan.side_effect = error
        return scanner

    discovery.side_effect = create_failing_discovery

    result = await start_dhcp_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    assert not hass.config_entries.async_entries(DOMAIN)
    assert discovery.instances[0].closed
    device.return_value.bind.assert_not_awaited()


@pytest.mark.parametrize(
    "disabled_by",
    [
        pytest.param(None, id="active-owner"),
        pytest.param(ConfigEntryDisabler.USER, id="disabled-owner"),
    ],
)
async def test_dhcp_does_not_scan_with_existing_owner(
    hass: HomeAssistant,
    discovery_entry: MockConfigEntry,
    discovery: MagicMock,
    disabled_by: ConfigEntryDisabler | None,
) -> None:
    """An active or disabled discovery owner prevents DHCP scans."""
    await hass.config_entries.async_set_disabled_by(
        discovery_entry.entry_id, disabled_by
    )

    result = await start_dhcp_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry]
    assert discovery_entry.disabled_by is disabled_by
    assert not discovery.instances


async def test_dhcp_does_not_scan_with_ignored_owner(
    hass: HomeAssistant,
    discovery_entry: MockConfigEntry,
    discovery: MagicMock,
) -> None:
    """An ignored discovery owner is preserved without scanning."""
    await hass.config_entries.async_remove(discovery_entry.entry_id)
    ignored = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=DOMAIN,
        source=config_entries.SOURCE_IGNORE,
        data={},
    )
    ignored.add_to_hass(hass)

    result = await start_dhcp_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [ignored]
    assert not discovery.instances


async def test_dhcp_announcements_share_one_pending_owner_flow(
    hass: HomeAssistant,
    discovery_entry: MockConfigEntry,
    discovery: MagicMock,
    device: MagicMock,
) -> None:
    """Multiple matching devices and DHCP announcements offer one owner."""
    await hass.config_entries.async_remove(discovery_entry.entry_id)
    second_info = DhcpServiceInfo(
        hostname="gree",
        ip="192.0.2.11",
        macaddress="0447caaabbcd",
    )
    discovery.mock_devices = [
        build_device_mock(
            ipAddress=DHCP_SERVICE_INFO.ip, identifier="04:47:CA:AA:BB:CC"
        ),
        build_device_mock(ipAddress=second_info.ip, identifier="04:47:CA:AA:BB:CD"),
    ]

    result = await start_dhcp_flow(hass)
    duplicate = await start_dhcp_flow(hass)
    other_device = await start_dhcp_flow(hass, second_info)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_discovery"
    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "already_in_progress"
    assert other_device["type"] is FlowResultType.ABORT
    assert other_device["reason"] == "already_in_progress"
    assert len(hass.config_entries.flow.async_progress()) == 1
    assert not hass.config_entries.async_entries(DOMAIN)
    device.return_value.bind.assert_not_awaited()


async def test_manual_add_racing_with_dhcp_uses_one_owner_flow(
    hass: HomeAssistant,
    discovery_entry: MockConfigEntry,
    discovery: MagicMock,
    device: MagicMock,
) -> None:
    """A manual add cannot race a pending DHCP owner confirmation."""
    await hass.config_entries.async_remove(discovery_entry.entry_id)
    discovery.mock_devices = [
        build_device_mock(
            ipAddress=DHCP_SERVICE_INFO.ip,
            identifier="04:47:CA:AA:BB:CC",
        )
    ]
    scan_started = asyncio.Event()
    release_scan = asyncio.Event()
    block_discovery_scan(discovery, scan_started, release_scan)
    dhcp_task = asyncio.create_task(start_dhcp_flow(hass))
    await scan_started.wait()

    manual = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    release_scan.set()
    result = await dhcp_task

    assert manual["type"] is FlowResultType.ABORT
    assert manual["reason"] == "already_in_progress"
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_discovery"
    assert len(hass.config_entries.flow.async_progress()) == 1
    assert not hass.config_entries.async_entries(DOMAIN)
    device.return_value.bind.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DOMAIN
    assert result["result"].source == config_entries.SOURCE_DHCP
    assert result["result"].data == {}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_dhcp_scan_rechecks_owner_created_while_awaiting(
    hass: HomeAssistant,
    discovery_entry: MockConfigEntry,
    discovery: MagicMock,
    device: MagicMock,
) -> None:
    """An owner added during DHCP scanning wins without being replaced."""
    await hass.config_entries.async_remove(discovery_entry.entry_id)
    discovery.mock_devices = [
        build_device_mock(
            ipAddress=DHCP_SERVICE_INFO.ip,
            identifier="04:47:CA:AA:BB:CC",
        )
    ]
    scan_started = asyncio.Event()
    release_scan = asyncio.Event()
    block_discovery_scan(discovery, scan_started, release_scan)
    dhcp_task = asyncio.create_task(start_dhcp_flow(hass))
    await scan_started.wait()
    winner = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=1,
        unique_id=DOMAIN,
        title="Gree discovery",
        data={},
    )
    winner.add_to_hass(hass)
    release_scan.set()

    result = await dhcp_task

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [winner]
    assert not hass.config_entries.flow.async_progress()
    device.return_value.bind.assert_not_awaited()


async def test_user_replaces_ignored_discovery_only_after_confirmation(
    hass: HomeAssistant,
    discovery_entry: MockConfigEntry,
    discovery: MagicMock,
) -> None:
    """Cancel preserves an ignored owner; confirmation replaces it."""
    await hass.config_entries.async_remove(discovery_entry.entry_id)
    ignored = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=DOMAIN,
        source=config_entries.SOURCE_IGNORE,
        data={},
    )
    ignored.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_discovery"
    assert hass.config_entries.async_entries(DOMAIN) == [ignored]
    assert not discovery.instances

    hass.config_entries.flow.async_abort(result["flow_id"])
    assert hass.config_entries.async_entries(DOMAIN) == [ignored]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == DOMAIN
    assert entry.source == config_entries.SOURCE_USER
    assert entry.version == 2
    assert entry.minor_version == 1
    assert entry.data == {}
    assert hass.config_entries.async_get_entry(ignored.entry_id) is None
    assert hass.config_entries.async_entries(DOMAIN) == [entry]


async def test_concurrent_initial_user_flows_create_one_discovery_entry(
    hass: HomeAssistant, discovery_entry: MockConfigEntry
) -> None:
    """Unique-ID flow rules prevent two initial discovery owners."""
    await hass.config_entries.async_remove(discovery_entry.entry_id)
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert first["type"] is FlowResultType.FORM
    assert first["step_id"] == "setup_discovery"
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_in_progress"
    created = await hass.config_entries.flow.async_configure(first["flow_id"], {})
    assert created["type"] is FlowResultType.CREATE_ENTRY
    assert created["result"].unique_id == DOMAIN
    assert hass.config_entries.async_entries(DOMAIN) == [created["result"]]


async def test_initial_setup_rechecks_existing_discovery_entry(
    hass: HomeAssistant, discovery_entry: MockConfigEntry
) -> None:
    """A setup form cannot overwrite a discovery owner created before submission."""
    await hass.config_entries.async_remove(discovery_entry.entry_id)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "setup_discovery"

    winner = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=1,
        unique_id=DOMAIN,
        title="Gree discovery",
        data={},
    )
    winner.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [winner]


@pytest.mark.parametrize("onboarded", [True, False])
async def test_discovery_requires_confirmation(
    hass: HomeAssistant,
    device: MagicMock,
    discovery_entry: MockConfigEntry,
    onboarded: bool,
    entity_registry: er.EntityRegistry,
) -> None:
    """Discovery never enrolls or binds an unknown unit without consent."""
    data = device_info_to_data(device().device_info)
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=onboarded,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=data,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {
        "name": data["name"],
        "identifier": data["identifier"],
        "host": data["host"],
    }
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry]
    assert not entity_registry.entities
    device().bind.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == data
    assert result["result"].unique_id == normalize_identifier(data["identifier"])
    assert result["result"].version == 2
    assert result["result"].minor_version == 1
    device().bind.assert_awaited_once_with()
    device().close.assert_called_once_with()


async def test_scan_selects_only_one_device(
    hass: HomeAssistant, device: MagicMock, discovery: MagicMock
) -> None:
    """Selection binds only its responder and persists the original wire identity."""
    other = build_device_mock("Other unit", "192.0.2.2", "AA:BB:CC:11:22:44")
    discovery.mock_devices = [device(), other]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "pick_device"
    device().bind.assert_not_awaited()
    other.bind.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: normalize_identifier(other.device_info.mac)}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aabbcc112244"
    assert result["data"] == device_info_to_data(other.device_info)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert device.call_args.args[0].mac == other.device_info.mac
    assert device.call_args.args[0].ip == other.device_info.ip
    assert device.call_args.args[0].port == other.device_info.port
    other.bind.assert_not_awaited()


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        pytest.param(None, "no_devices_found", id="empty"),
        pytest.param(OSError, "cannot_connect", id="network-error"),
        pytest.param(TimeoutError, "cannot_connect", id="timeout"),
    ],
)
async def test_scan_empty_or_error(
    hass: HomeAssistant, failure: type[Exception] | None, reason: str
) -> None:
    """A failed scan is distinct from a successful empty LAN scan."""
    with patch(
        "homeassistant.components.gree.config_flow.async_get_discovery"
    ) as scanner:
        scanner.return_value.async_scan = AsyncMock(
            return_value={}, side_effect=failure
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_scan_filters_configured_identities(
    hass: HomeAssistant, device: MagicMock, discovery: MagicMock
) -> None:
    """Scanning offers unconfigured responders without affecting known units."""
    known = add_entry(hass, device_info_to_data(device().device_info))
    other = build_device_mock("Other", "192.0.2.2", "aabbcc112244")
    discovery.mock_devices = [device(), other]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "pick_device"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: other.device_info.mac}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == other.device_info.mac
    assert hass.config_entries.async_get_entry(known.entry_id) is known
    assert len(hass.config_entries.async_entries(DOMAIN)) == 3


async def test_all_candidates_configured(
    hass: HomeAssistant,
    device: MagicMock,
    discovery: MagicMock,
) -> None:
    """No selection form is shown when every discovered identity is configured."""
    other = build_device_mock("Other", "192.0.2.2", "aabbcc112244")
    discovery.mock_devices = [device(), other]
    add_entry(hass, device_info_to_data(device().device_info))
    add_entry(hass, device_info_to_data(other.device_info))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    device().bind.assert_not_awaited()


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        pytest.param(DeviceNotBoundError, "cannot_connect", id="not-bound"),
        pytest.param(DeviceTimeoutError, "cannot_connect", id="device-timeout"),
        pytest.param(OSError, "cannot_connect", id="network-error"),
        pytest.param(TimeoutError, "cannot_connect", id="timeout"),
        pytest.param(RuntimeError, "unknown", id="unexpected"),
    ],
)
@pytest.mark.parametrize("step", ["pick_device", "discovery_confirm"])
async def test_selected_validation_failure(
    hass: HomeAssistant,
    device: MagicMock,
    discovery_entry: MockConfigEntry,
    failure: type[Exception],
    error: str,
    step: str,
) -> None:
    """Connection errors preserve the active form and always close validation."""
    data = device_info_to_data(device().device_info)
    with patch(
        "homeassistant.components.gree.config_flow.async_bind_device",
        side_effect=failure,
    ):
        result = await start_selected_step(hass, step, data)
        submission = {
            "pick_device": {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])},
            "discovery_confirm": {},
        }[step]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], submission
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step
    assert result["errors"] == {"base": error}
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry]
    device().close.assert_called_once_with()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], submission
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aabbcc112233"
    assert result["data"] == data
    device().bind.assert_awaited_once_with()
    assert device().close.call_count == 2


async def start_selected_step(
    hass: HomeAssistant, step: str, data: dict[str, Any]
) -> config_entries.ConfigFlowResult:
    """Reach a selected-device form through the public flow manager."""
    if step == "discovery_confirm":
        return await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=data,
        )
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


@pytest.mark.parametrize("step", ["pick_device", "discovery_confirm"])
async def test_validation_cancelled(
    hass: HomeAssistant,
    device: MagicMock,
    discovery_entry: MockConfigEntry,
    step: str,
) -> None:
    """Cancellation propagates rather than becoming a connection error form."""
    data = device_info_to_data(device().device_info)
    result = await start_selected_step(hass, step, data)
    submission = {
        "pick_device": {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])},
        "discovery_confirm": {},
    }[step]
    with (
        patch(
            "homeassistant.components.gree.config_flow.async_bind_device",
            side_effect=asyncio.CancelledError,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await hass.config_entries.flow.async_configure(result["flow_id"], submission)
    device().close.assert_called_once_with()
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry]


@pytest.mark.parametrize("step", ["pick_device", "discovery_confirm"])
async def test_shutdown_during_selected_binding(
    hass: HomeAssistant,
    device: MagicMock,
    discovery: MagicMock,
    discovery_entry: MockConfigEntry,
    step: str,
) -> None:
    """Shutdown cancels active and queued selected bindings before bind."""
    await hass.async_start()
    assert await async_setup_component(hass, DOMAIN, {})

    first_candidate = build_device_mock()
    second_candidate = build_device_mock("Other unit", "192.0.2.2", "AA:BB:CC:11:22:44")
    discovery.mock_devices = [first_candidate, second_candidate]
    first_data = device_info_to_data(first_candidate.device_info)
    second_data = device_info_to_data(second_candidate.device_info)
    first_flow = await start_selected_step(hass, step, first_data)
    second_flow = await start_selected_step(hass, step, second_data)
    first_submission = {
        "pick_device": {CONF_DEVICE: normalize_identifier(first_data[CONF_IDENTIFIER])},
        "discovery_confirm": {},
    }[step]
    second_submission = {
        "pick_device": {
            CONF_DEVICE: normalize_identifier(second_data[CONF_IDENTIFIER])
        },
        "discovery_confirm": {},
    }[step]

    first_bound_device = build_device_mock()
    second_bound_device = build_device_mock(
        "Other unit", "192.0.2.2", "AA:BB:CC:11:22:44"
    )
    device.side_effect = [first_bound_device, second_bound_device]

    started = asyncio.Event()
    release = asyncio.Event()

    async def delayed_scan(**kwargs: Any) -> list[Any]:
        started.set()
        await release.wait()
        return [first_candidate.device_info, second_candidate.device_info]

    active = Mock(scan=AsyncMock(side_effect=delayed_scan), close=Mock())
    discovery.side_effect = [active]
    scanner = async_get_discovery(hass)
    scan_requests: asyncio.Queue[None] = asyncio.Queue()
    original_scan = scanner.async_scan

    async def selected_scan(*, wait_for: int) -> dict[str, Any]:
        scan_requests.put_nowait(None)
        return await original_scan(wait_for=wait_for)

    with patch.object(scanner, "async_scan", side_effect=selected_scan):
        active_selection = asyncio.create_task(
            hass.config_entries.flow.async_configure(
                first_flow["flow_id"], first_submission
            )
        )
        await scan_requests.get()
        await started.wait()
        queued_selection = asyncio.create_task(
            hass.config_entries.flow.async_configure(
                second_flow["flow_id"], second_submission
            )
        )
        await scan_requests.get()

        await hass.async_stop()
        release.set()
        results = await asyncio.gather(
            active_selection, queued_selection, return_exceptions=True
        )

    assert all(isinstance(result, asyncio.CancelledError) for result in results)
    active.scan.assert_awaited_once()
    active.close.assert_called()
    first_bound_device.close.assert_called_once_with()
    second_bound_device.close.assert_called_once_with()
    first_bound_device.bind.assert_not_awaited()
    second_bound_device.bind.assert_not_awaited()
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry]


@pytest.mark.parametrize(
    ("state", "reload"),
    [
        (ConfigEntryState.LOADED, True),
        (ConfigEntryState.SETUP_ERROR, True),
        (ConfigEntryState.SETUP_RETRY, True),
        (ConfigEntryState.NOT_LOADED, True),
        (ConfigEntryState.SETUP_IN_PROGRESS, True),
        (ConfigEntryState.MIGRATION_ERROR, False),
        (ConfigEntryState.FAILED_UNLOAD, False),
        (ConfigEntryState.UNLOAD_IN_PROGRESS, False),
    ],
)
@pytest.mark.parametrize("changed", [CONF_HOST, CONF_PORT])
async def test_known_endpoint_update(
    hass: HomeAssistant,
    device: MagicMock,
    state: ConfigEntryState,
    reload: bool,
    changed: str,
) -> None:
    """Changed endpoints persist and reload only states Core can safely recover."""
    data = device_info_to_data(device().device_info)
    stored = {
        **data,
        CONF_IDENTIFIER: "AA:BB:CC:11:22:33",
    }
    entry = add_entry(hass, stored, state=state)
    observed = {**data, changed: {CONF_HOST: "192.0.2.2", CONF_PORT: 7001}[changed]}
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=observed,
        )
        assert schedule.call_count == int(reload)
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=observed,
        )
        assert schedule.call_count == int(reload)
    assert result["reason"] == "already_configured"
    assert entry.data == {
        **observed,
        CONF_IDENTIFIER: stored[CONF_IDENTIFIER],
    }
    assert entry.title == "User chosen title"
    device().bind.assert_not_awaited()


@pytest.mark.parametrize("metadata", [{}, {"name": "New name", "model": "New model"}])
async def test_known_unchanged_endpoint(
    hass: HomeAssistant, device: MagicMock, metadata: dict[str, str]
) -> None:
    """Neither unchanged nor metadata-only observations reload a retrying unit."""
    data = device_info_to_data(device().device_info)
    entry = add_entry(hass, data, state=ConfigEntryState.SETUP_RETRY)
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={**data, **metadata},
        )
    assert result["reason"] == "already_configured"
    assert entry.data == {**data, **metadata}
    schedule.assert_not_called()
    device().bind.assert_not_awaited()


async def test_disabled_entry_endpoint_update(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """Discovery saves disabled devices' addresses without enabling or reloading."""
    data = device_info_to_data(device().device_info)
    entry = add_entry(hass, data, disabled_by=ConfigEntryDisabler.USER)
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={**data, CONF_HOST: "192.0.2.2"},
        )
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.0.2.2"
    assert entry.disabled_by is ConfigEntryDisabler.USER
    schedule.assert_not_called()
    device().bind.assert_not_awaited()


async def test_background_ignored_entry_untouched(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """An ignored identifier is not bound, updated or offered again."""
    data = device_info_to_data(device().device_info)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=normalize_identifier(data[CONF_IDENTIFIER]),
        source=config_entries.SOURCE_IGNORE,
        title="Ignored",
        data={},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data=data,
    )
    assert result["reason"] == "already_configured"
    assert entry.data == {}
    assert entry.title == "Ignored"
    device().bind.assert_not_awaited()


async def test_explicit_selection_replaces_ignore(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """Only explicit user selection replaces an ignored entry."""
    data = device_info_to_data(device().device_info)
    ignored = MockConfigEntry(
        domain=DOMAIN,
        unique_id=normalize_identifier(data[CONF_IDENTIFIER]),
        source=config_entries.SOURCE_IGNORE,
    )
    ignored.add_to_hass(hass)
    result = await start_selected_step(hass, "pick_device", data)
    assert hass.config_entries.async_get_entry(ignored.entry_id) is ignored
    device().bind.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aabbcc112233"
    assert result["result"].source == config_entries.SOURCE_USER
    assert result["result"].data == data
    assert hass.config_entries.async_get_entry(ignored.entry_id) is None
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_background_deduplication(
    hass: HomeAssistant, device: MagicMock, discovery_entry: MockConfigEntry
) -> None:
    """Alternate identifier spellings share one discovery confirmation."""
    data = device_info_to_data(device().device_info)
    first = await start_selected_step(hass, "discovery_confirm", data)
    second = await start_selected_step(
        hass, "discovery_confirm", {**data, CONF_IDENTIFIER: "AA-BB-CC-11-22-33"}
    )
    assert first["step_id"] == "discovery_confirm"
    assert second["reason"] == "already_in_progress"
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
    device().bind.assert_not_awaited()


async def test_pending_discovery_endpoint_update(
    hass: HomeAssistant,
    device: MagicMock,
    discovery_entry: MockConfigEntry,
) -> None:
    """Rediscovery refreshes one confirmation without binding before consent."""
    data = device_info_to_data(device().device_info)
    pending = await start_selected_step(hass, "discovery_confirm", data)
    observed = {
        **data,
        CONF_HOST: "192.0.2.2",
        CONF_PORT: 7001,
        CONF_IDENTIFIER: "AA-BB-CC-11-22-33",
        "name": "Updated name",
    }
    duplicate = await start_selected_step(hass, "discovery_confirm", observed)
    assert duplicate["reason"] == "already_in_progress"
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry]
    device().bind.assert_not_awaited()
    placeholders = {
        "name": observed["name"],
        "identifier": data[CONF_IDENTIFIER],
        "host": observed[CONF_HOST],
    }
    assert (
        hass.config_entries.flow.async_get(pending["flow_id"])["context"][
            "title_placeholders"
        ]
        == placeholders
    )
    refreshed = await hass.config_entries.flow.async_configure(pending["flow_id"])
    assert refreshed["step_id"] == "discovery_confirm"
    assert refreshed["description_placeholders"] == placeholders
    device().bind.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(pending["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**observed, CONF_IDENTIFIER: data[CONF_IDENTIFIER]}
    assert result["title"] == observed["name"]
    assert result["result"].unique_id == normalize_identifier(data[CONF_IDENTIFIER])
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert device.call_args.args[0].ip == observed[CONF_HOST]
    assert device.call_args.args[0].port == observed[CONF_PORT]
    assert device.call_args.args[0].mac == data[CONF_IDENTIFIER]
    device().bind.assert_awaited_once_with()
    device().close.assert_called_once_with()


async def test_background_discovery_endpoint_returns_to_original_address(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """Background deduplication cannot suppress an address returning to its origin."""
    data = device_info_to_data(device().device_info)
    await hass.async_start()
    for observed in (data, {**data, CONF_HOST: "192.0.2.2"}, data):
        discovery_flow.async_create_flow(
            hass,
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=observed,
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    pending = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(pending) == 1
    device().bind.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(pending[0]["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == data
    assert result["result"].unique_id == normalize_identifier(data[CONF_IDENTIFIER])
    assert device.call_args.args[0].ip == data[CONF_HOST]


async def test_pending_discovery_failure_endpoint_update(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """A failed confirmation retries the new endpoint rather than the old one."""
    data = device_info_to_data(device().device_info)
    pending = await start_selected_step(hass, "discovery_confirm", data)
    device().bind.side_effect = DeviceTimeoutError
    failed = await hass.config_entries.flow.async_configure(pending["flow_id"], {})
    assert failed["errors"] == {"base": "cannot_connect"}
    assert device.call_args.args[0].ip == data[CONF_HOST]
    device().bind.reset_mock()
    observed = {**data, CONF_HOST: "192.0.2.2", CONF_PORT: 7001}
    duplicate = await start_selected_step(hass, "discovery_confirm", observed)
    assert duplicate["reason"] == "already_in_progress"
    device().bind.assert_not_awaited()
    device().bind.side_effect = None

    result = await hass.config_entries.flow.async_configure(pending["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == observed
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert device.call_args.args[0].ip == observed[CONF_HOST]
    assert device.call_args.args[0].port == observed[CONF_PORT]


async def test_failed_manual_selection_does_not_block_rediscovery(
    hass: HomeAssistant, device: MagicMock, discovery_entry: MockConfigEntry
) -> None:
    """Failed manual enrollment cannot suppress discovery at a new endpoint."""
    data = device_info_to_data(device().device_info)
    manual = await start_selected_step(hass, "pick_device", data)
    device().bind.side_effect = DeviceTimeoutError
    failed = await hass.config_entries.flow.async_configure(
        manual["flow_id"], {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])}
    )
    assert failed["errors"] == {"base": "cannot_connect"}
    device().bind.reset_mock()
    device().bind.side_effect = None

    observed = {**data, CONF_HOST: "192.0.2.2", CONF_PORT: 7001}
    device().device_info.ip = observed[CONF_HOST]
    device().device_info.port = observed[CONF_PORT]
    discovered = await start_selected_step(hass, "discovery_confirm", observed)
    assert discovered["type"] is FlowResultType.FORM
    assert discovered["step_id"] == "discovery_confirm"
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry]
    device().bind.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(discovered["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == observed
    assert device.call_args.args[0].ip == observed[CONF_HOST]
    assert device.call_args.args[0].port == observed[CONF_PORT]
    assert manual["flow_id"] not in {
        flow["flow_id"]
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    }


async def test_failed_manual_selection_refreshes_candidate_before_retry(
    hass: HomeAssistant, device: MagicMock, discovery: MagicMock
) -> None:
    """A manual retry binds the selected identity at its latest endpoint."""
    binding_device = device()
    binding_device.device_info.mac = "AA:BB:CC:11:22:33"
    data = device_info_to_data(binding_device.device_info)
    manual = await start_selected_step(hass, "pick_device", data)
    binding_device.bind.side_effect = DeviceTimeoutError
    failed = await hass.config_entries.flow.async_configure(
        manual["flow_id"], {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])}
    )
    assert failed["errors"] == {"base": "cannot_connect"}
    binding_device.bind.reset_mock()
    binding_device.bind.side_effect = None

    updated = build_device_mock(
        "Updated unit", "192.0.2.2", "aa-bb-cc-11-22-33", port=7001
    )
    discovery.mock_devices = [updated]
    result = await hass.config_entries.flow.async_configure(
        manual["flow_id"], {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])}
    )

    expected = {
        **device_info_to_data(updated.device_info),
        CONF_IDENTIFIER: data[CONF_IDENTIFIER],
    }
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == expected
    assert result["result"].unique_id == normalize_identifier(data[CONF_IDENTIFIER])
    assert device.call_args.args[0].ip == "192.0.2.2"
    assert device.call_args.args[0].port == 7001
    assert device.call_args.args[0].mac == data[CONF_IDENTIFIER]
    binding_device.bind.assert_awaited_once_with()


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(None, id="selected-device-missing"),
        pytest.param(OSError, id="scan-error"),
        pytest.param(TimeoutError, id="scan-timeout"),
    ],
)
async def test_failed_manual_retry_without_fresh_candidate(
    hass: HomeAssistant,
    device: MagicMock,
    discovery_entry: MockConfigEntry,
    failure: type[Exception] | None,
) -> None:
    """Missing responders and failed retry scans keep the pick-device form."""
    binding_device = device()
    data = device_info_to_data(binding_device.device_info)
    manual = await start_selected_step(hass, "pick_device", data)
    binding_device.bind.side_effect = DeviceTimeoutError
    failed = await hass.config_entries.flow.async_configure(
        manual["flow_id"], {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])}
    )
    assert failed["errors"] == {"base": "cannot_connect"}
    binding_device.bind.reset_mock()
    binding_device.bind.side_effect = None

    scanner = MagicMock(async_scan=AsyncMock(return_value={}, side_effect=failure))
    with patch(
        "homeassistant.components.gree.config_flow.async_get_discovery",
        return_value=scanner,
    ):
        result = await hass.config_entries.flow.async_configure(
            manual["flow_id"],
            {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_device"
    assert result["errors"] == {"base": "cannot_connect"}
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry]
    scanner.async_scan.assert_awaited_once_with()
    binding_device.bind.assert_not_awaited()

    recovered = await hass.config_entries.flow.async_configure(
        manual["flow_id"],
        {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])},
    )
    assert recovered["type"] is FlowResultType.CREATE_ENTRY
    assert recovered["data"] == data
    assert recovered["result"].unique_id == normalize_identifier(data[CONF_IDENTIFIER])
    assert hass.config_entries.async_entries(DOMAIN) == [
        discovery_entry,
        recovered["result"],
    ]
    binding_device.bind.assert_awaited_once_with()


async def test_manual_retry_rechecks_entry_after_scan(
    hass: HomeAssistant, device: MagicMock, discovery_entry: MockConfigEntry
) -> None:
    """A config entry created during retry scanning wins over the selection."""
    binding_device = device()
    data = device_info_to_data(binding_device.device_info)
    manual = await start_selected_step(hass, "pick_device", data)
    binding_device.bind.side_effect = DeviceTimeoutError
    failed = await hass.config_entries.flow.async_configure(
        manual["flow_id"], {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])}
    )
    assert failed["errors"] == {"base": "cannot_connect"}
    binding_device.bind.reset_mock()
    binding_device.bind.side_effect = None

    winning_results: list[dict[str, Any]] = []

    winner_device = build_device_mock()

    async def scan_and_add_winner() -> dict[str, Any]:
        winner_flow = await start_selected_step(hass, "discovery_confirm", data)
        with patch(
            "homeassistant.components.gree.config_flow.Device",
            return_value=winner_device,
        ):
            winner_result = await hass.config_entries.flow.async_configure(
                winner_flow["flow_id"], {}
            )
        winning_results.append(winner_result)
        return {}

    scanner = MagicMock(async_scan=AsyncMock(side_effect=scan_and_add_winner))
    with patch(
        "homeassistant.components.gree.config_flow.async_get_discovery",
        return_value=scanner,
    ):
        result = await hass.config_entries.flow.async_configure(
            manual["flow_id"],
            {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])},
        )

    assert winning_results[0]["type"] is FlowResultType.CREATE_ENTRY
    assert winning_results[0]["data"] == data
    assert winning_results[0]["result"].unique_id == normalize_identifier(
        data[CONF_IDENTIFIER]
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [
        discovery_entry,
        winning_results[0]["result"],
    ]
    scanner.async_scan.assert_awaited_once_with()
    binding_device.bind.assert_not_awaited()
    winner_device.bind.assert_awaited_once_with()


@pytest.mark.parametrize("failure", [None, DeviceTimeoutError])
async def test_pending_discovery_update_during_validation(
    hass: HomeAssistant,
    device: MagicMock,
    discovery_entry: MockConfigEntry,
    failure: type[Exception] | None,
) -> None:
    """An in-flight snapshot cannot enroll or restore an obsolete endpoint."""
    data = device_info_to_data(device().device_info)
    pending = await start_selected_step(hass, "discovery_confirm", data)
    observed = {**data, CONF_HOST: "192.0.2.2", CONF_PORT: 7001}
    binding = asyncio.Event()
    release = asyncio.Event()
    outcome = AsyncMock(side_effect=failure)

    async def bind_snapshot(*args: object) -> None:
        binding.set()
        await release.wait()
        await outcome()

    with patch(
        "homeassistant.components.gree.config_flow.async_bind_device",
        side_effect=bind_snapshot,
    ) as bind:
        task = hass.async_create_task(
            hass.config_entries.flow.async_configure(pending["flow_id"], {})
        )
        await binding.wait()
        snapshot = device.call_args.args[0]
        duplicate = await start_selected_step(hass, "discovery_confirm", observed)
        assert duplicate["reason"] == "already_in_progress"
        assert snapshot.ip == data[CONF_HOST]
        assert snapshot.port == data[CONF_PORT]
        bind.assert_awaited_once()
        release.set()
        result = await task

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"]["host"] == observed[CONF_HOST]
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry]
    device().bind.assert_not_awaited()
    refreshed = await hass.config_entries.flow.async_configure(pending["flow_id"])
    assert refreshed["description_placeholders"]["host"] == observed[CONF_HOST]
    result = await hass.config_entries.flow.async_configure(pending["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == observed
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert device.call_args.args[0].ip == observed[CONF_HOST]
    assert device.call_args.args[0].port == observed[CONF_PORT]
    device().bind.assert_awaited_once_with()
    assert device().close.call_count == 2


@pytest.mark.parametrize(
    "metadata",
    [
        pytest.param({}, id="unchanged"),
        pytest.param({"name": "Updated name", "model": "Updated model"}, id="metadata"),
        pytest.param({CONF_IDENTIFIER: "AA-BB-CC-11-22-33"}, id="identifier-spelling"),
    ],
)
async def test_pending_discovery_metadata_during_validation(
    hass: HomeAssistant, device: MagicMock, metadata: dict[str, str]
) -> None:
    """Rediscovery at the same endpoint does not invalidate an in-flight bind."""
    data = device_info_to_data(device().device_info)
    pending = await start_selected_step(hass, "discovery_confirm", data)
    observed = {**data, **metadata}
    binding = asyncio.Event()
    release = asyncio.Event()

    async def bind_snapshot(*args: object) -> None:
        binding.set()
        await release.wait()

    with patch(
        "homeassistant.components.gree.config_flow.async_bind_device",
        side_effect=bind_snapshot,
    ) as bind:
        task = hass.async_create_task(
            hass.config_entries.flow.async_configure(pending["flow_id"], {})
        )
        await binding.wait()
        snapshot = device.call_args.args[0]
        duplicate = await start_selected_step(hass, "discovery_confirm", observed)
        assert duplicate["reason"] == "already_in_progress"
        assert snapshot.name == data["name"]
        assert snapshot.mac == data[CONF_IDENTIFIER]
        bind.assert_awaited_once()
        release.set()
        result = await task

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**observed, CONF_IDENTIFIER: data[CONF_IDENTIFIER]}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    device().close.assert_called_once_with()


async def test_user_can_enroll_pending_background_candidate(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """A pending discovery card cannot block explicit selection."""
    data = device_info_to_data(device().device_info)
    background = await start_selected_step(hass, "discovery_confirm", data)
    user = await start_selected_step(hass, "pick_device", data)
    user = await hass.config_entries.flow.async_configure(
        user["flow_id"], {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])}
    )
    assert user["type"] is FlowResultType.CREATE_ENTRY
    assert user["result"].unique_id == "aabbcc112233"
    assert background["flow_id"] not in {
        flow["flow_id"]
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    device().bind.assert_awaited_once_with()


@pytest.mark.parametrize("step", ["pick_device", "discovery_confirm"])
async def test_entry_created_during_validation(
    hass: HomeAssistant,
    device: MagicMock,
    discovery_entry: MockConfigEntry,
    step: str,
) -> None:
    """Another winning flow is never replaced after the network await."""
    data = device_info_to_data(device().device_info)
    result = await start_selected_step(hass, step, data)
    winners: list[MockConfigEntry] = []

    async def another_flow_wins(*args: object) -> None:
        winners.append(add_entry(hass, {**data, CONF_HOST: "192.0.2.99"}))

    with (
        patch(
            "homeassistant.components.gree.config_flow.async_bind_device",
            side_effect=another_flow_wins,
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as schedule,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "pick_device": {
                    CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])
                },
                "discovery_confirm": {},
            }[step],
        )
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry, *winners]
    assert winners[0].data[CONF_HOST] == "192.0.2.99"
    schedule.assert_not_called()
    device().close.assert_called_once_with()


async def test_pick_device_rejects_unoffered_identity(
    hass: HomeAssistant, device: MagicMock, discovery_entry: MockConfigEntry
) -> None:
    """The selector accepts only identities in the server-side scan results."""
    result = await start_selected_step(
        hass, "pick_device", device_info_to_data(device().device_info)
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "not-a-discovered-device"}
        )
    device().bind.assert_not_awaited()
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry]


@pytest.mark.parametrize("step", ["pick_device", "discovery_confirm"])
async def test_candidate_configured_before_submission(
    hass: HomeAssistant,
    device: MagicMock,
    discovery_entry: MockConfigEntry,
    step: str,
) -> None:
    """A concurrently configured device cannot be rebound or have its endpoint replaced."""
    data = device_info_to_data(device().device_info)
    result = await start_selected_step(hass, step, data)
    entry = add_entry(hass, {**data, CONF_HOST: "192.0.2.99"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "pick_device": {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])},
            "discovery_confirm": {},
        }[step],
    )
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry, entry]
    assert entry.data[CONF_HOST] == "192.0.2.99"
    device().bind.assert_not_awaited()


async def test_known_entry_precedes_pending_flow_check(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """A pending confirmation cannot prevent endpoint repair for a known unit."""
    data = device_info_to_data(device().device_info)
    pending = await start_selected_step(hass, "discovery_confirm", data)
    entry = add_entry(hass, {**data, CONF_HOST: "192.0.2.99"})
    with patch.object(hass.config_entries, "async_schedule_reload") as schedule:
        result = await start_selected_step(hass, "discovery_confirm", data)
    assert result["reason"] == "already_configured"
    assert entry.data == data
    schedule.assert_called_once_with(entry.entry_id)
    assert (
        hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]["flow_id"]
        == pending["flow_id"]
    )
    device().bind.assert_not_awaited()


async def test_scan_cancellation_propagates(
    hass: HomeAssistant, discovery_entry: MockConfigEntry
) -> None:
    """A cancelled scan does not become an empty-LAN or connection error."""
    with patch(
        "homeassistant.components.gree.config_flow.async_get_discovery"
    ) as scanner:
        scanner.return_value.async_scan = AsyncMock(side_effect=asyncio.CancelledError)
        with pytest.raises(asyncio.CancelledError):
            await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
    assert hass.config_entries.async_entries(DOMAIN) == [discovery_entry]


async def test_concurrent_user_and_discovery_validation(
    hass: HomeAssistant, device: MagicMock, discovery_entry: MockConfigEntry
) -> None:
    """Two consenting flows racing through binding leave exactly one entry."""
    data = device_info_to_data(device().device_info)
    background = await start_selected_step(hass, "discovery_confirm", data)
    user = await start_selected_step(hass, "pick_device", data)
    background_bound = asyncio.Event()
    user_bound = asyncio.Event()
    release_background = asyncio.Event()
    release_user = asyncio.Event()

    async def background_bind(*args: object) -> None:
        background_bound.set()
        await release_background.wait()

    async def user_bind(*args: object) -> None:
        user_bound.set()
        await release_user.wait()

    with patch(
        "homeassistant.components.gree.config_flow.async_bind_device",
        side_effect=background_bind,
    ) as bind:
        background_task = hass.async_create_task(
            hass.config_entries.flow.async_configure(background["flow_id"], {})
        )
        await background_bound.wait()
        bind.side_effect = user_bind
        user_task = hass.async_create_task(
            hass.config_entries.flow.async_configure(
                user["flow_id"],
                {CONF_DEVICE: normalize_identifier(data[CONF_IDENTIFIER])},
            )
        )
        await user_bound.wait()
        release_user.set()
        user_result = await user_task
        release_background.set()
        background_result = await background_task
    assert user_result["type"] is FlowResultType.CREATE_ENTRY
    assert user_result["result"].unique_id == "aabbcc112233"
    assert background_result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [
        discovery_entry,
        user_result["result"],
    ]
    assert user_result["result"].data == data
    assert device().close.call_count == 2
