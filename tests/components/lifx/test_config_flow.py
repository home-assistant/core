"""Tests for the LIFX integration config flow."""

from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import contextmanager
from dataclasses import replace
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

from lifx import (
    DiscoveredDevice,
    LifxDeviceNotFoundError,
    LifxUnsupportedDeviceError,
    Light,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.lifx import DOMAIN
from homeassistant.components.lifx.config_flow import LIFXConfigFlow
from homeassistant.components.lifx.const import CONF_SERIAL
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import DHCP_FORMATTED_MAC, IP_ADDRESS, LABEL, SERIAL
from .helpers import LEGACY_SERIAL

from tests.common import MockConfigEntry

OLD_IP_ADDRESS = "127.0.0.2"

DiscoveryData = DhcpServiceInfo | ZeroconfServiceInfo | dict[str, str]
DeviceMutator = Callable[[Light], None]


def _remove_light_state(mock_light: Light) -> None:
    """Remove the state returned after refresh."""
    mock_light.state = None


def _fail_light_refresh(mock_light: Light) -> None:
    """Fail the public state refresh."""
    mock_light.refresh_state.side_effect = OSError("refresh failed")


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override config entry setup."""
    with patch(
        "homeassistant.components.lifx.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


def _zeroconf_info(*, serial: object = SERIAL) -> ZeroconfServiceInfo:
    """Return LIFX mDNS discovery data."""
    return ZeroconfServiceInfo(
        ip_address=IPv4Address(IP_ADDRESS),
        ip_addresses=[IPv4Address(IP_ADDRESS)],
        port=56700,
        hostname="my-bulb.local.",
        name="My Bulb._lifx._udp.local.",
        properties={"id": serial},
        type="_lifx._udp.local.",
    )


def _zeroconf_info_without_serial() -> ZeroconfServiceInfo:
    """Return LIFX mDNS discovery data without an identity property."""
    return replace(_zeroconf_info(), properties={})


def _homekit_info() -> ZeroconfServiceInfo:
    """Return HomeKit discovery data."""
    return ZeroconfServiceInfo(
        ip_address=IPv4Address(IP_ADDRESS),
        ip_addresses=[IPv4Address(IP_ADDRESS)],
        port=None,
        hostname="my-bulb.local.",
        name=LABEL,
        properties={"id": "ignored"},
        type="mock_type",
    )


def _dhcp_info(mac: str = DHCP_FORMATTED_MAC) -> DhcpServiceInfo:
    """Return DHCP discovery data."""
    return DhcpServiceInfo(ip=IP_ADDRESS, macaddress=mac, hostname=LABEL)


SERIAL_DISCOVERY_SOURCES = [
    pytest.param(config_entries.SOURCE_ZEROCONF, _zeroconf_info(), id="mdns"),
    pytest.param(
        config_entries.SOURCE_INTEGRATION_DISCOVERY,
        {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL},
        id="broadcast",
    ),
]
DISCOVERY_SOURCES = [
    *SERIAL_DISCOVERY_SOURCES,
    pytest.param(config_entries.SOURCE_DHCP, _dhcp_info(), id="dhcp"),
    pytest.param(config_entries.SOURCE_HOMEKIT, _homekit_info(), id="homekit"),
]


@contextmanager
def _mock_broadcast_discovery(
    *devices: DiscoveredDevice,
) -> Generator[None]:
    """Patch the public broadcast discovery generator."""

    async def _discover_devices(
        **kwargs: str | float,
    ) -> AsyncGenerator[DiscoveredDevice]:
        for device in devices:
            yield device

    with patch(
        "homeassistant.components.lifx.discovery.discover_devices",
        _discover_devices,
    ):
        yield


async def test_zeroconf_discovery_creates_version_2_entry(
    hass: HomeAssistant, mock_light: Light
) -> None:
    """Test mDNS discovery creates a per-device version 2 entry."""
    with patch(
        "homeassistant.components.lifx.config_flow.Device.connect",
        return_value=mock_light,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=_zeroconf_info(),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == LABEL
    assert result["data"] == {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL}
    assert result["result"].unique_id == SERIAL
    assert result["result"].version == 2
    mock_light.close.assert_awaited_once_with()


async def test_discovery_during_onboarding_skips_confirmation(
    hass: HomeAssistant, mock_light: Light
) -> None:
    """Test a device discovered before onboarding finishes is added on its own."""
    with (
        patch(
            "homeassistant.components.lifx.config_flow.Device.connect",
            return_value=mock_light,
        ),
        patch(
            "homeassistant.components.onboarding.async_is_onboarded",
            return_value=False,
        ) as mock_onboarding,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=_zeroconf_info(),
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == LABEL
    assert result["data"] == {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL}
    assert result["result"].unique_id == SERIAL
    assert len(mock_onboarding.mock_calls) == 1


@pytest.mark.parametrize(("source", "data"), SERIAL_DISCOVERY_SOURCES)
@pytest.mark.parametrize(
    ("entry_version", "entry_data"),
    [
        pytest.param(1, {CONF_HOST: OLD_IP_ADDRESS}, id="version-1"),
        pytest.param(
            2,
            {CONF_HOST: OLD_IP_ADDRESS, CONF_SERIAL: SERIAL},
            id="version-2",
        ),
    ],
)
async def test_serial_discovery_repairs_configured_entry(
    hass: HomeAssistant,
    source: str,
    data: DiscoveryData,
    entry_version: int,
    entry_data: dict[str, str],
) -> None:
    """Test serial discovery repairs entries of either stored version."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=entry_data,
        unique_id=SERIAL,
        version=entry_version,
        state=config_entries.ConfigEntryState.LOADED,
    )
    config_entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data == {**entry_data, CONF_HOST: IP_ADDRESS}
    mock_reload.assert_called_once_with(config_entry.entry_id)
    config_entry.mock_state(hass, config_entries.ConfigEntryState.NOT_LOADED)


@pytest.mark.parametrize(
    "dhcp_mac",
    [
        pytest.param("d073d5ddeecc", id="serial-mac"),
        pytest.param("d073d5ddeecd", id="firmware-offset-mac"),
    ],
)
async def test_dhcp_repairs_entry_for_each_serial_mac_candidate(
    hass: HomeAssistant, dhcp_mac: str
) -> None:
    """Test DHCP matches both MAC addresses derived from a device serial."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: OLD_IP_ADDRESS, CONF_SERIAL: SERIAL},
        unique_id=SERIAL,
        version=2,
        state=config_entries.ConfigEntryState.LOADED,
    )
    config_entry.add_to_hass(hass)

    with (
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
        patch(
            "homeassistant.components.lifx.config_flow.mac_candidates_for_serial",
            return_value=(SERIAL, "d0:73:d5:dd:ee:cd"),
        ),
        patch(
            "homeassistant.components.lifx.config_flow.find_by_ip",
            side_effect=AssertionError("DHCP matching must happen before probing"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=_dhcp_info(dhcp_mac),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == IP_ADDRESS
    mock_reload.assert_called_once_with(config_entry.entry_id)
    config_entry.mock_state(hass, config_entries.ConfigEntryState.NOT_LOADED)


async def test_dhcp_repairs_entry_that_has_not_been_migrated(
    hass: HomeAssistant,
) -> None:
    """Test DHCP matches an entry that still holds a colon separated unique ID."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: OLD_IP_ADDRESS},
        unique_id=LEGACY_SERIAL,
        version=1,
        disabled_by=config_entries.ConfigEntryDisabler.USER,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lifx.config_flow.find_by_ip",
        side_effect=AssertionError("DHCP matching must happen before probing"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=_dhcp_info(),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == IP_ADDRESS
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_homekit_repairs_entry_identified_by_ip(
    hass: HomeAssistant, mock_light: Light
) -> None:
    """Test HomeKit discovery identifies by IP before repairing an entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: OLD_IP_ADDRESS, CONF_SERIAL: SERIAL},
        unique_id=SERIAL,
        version=2,
        state=config_entries.ConfigEntryState.LOADED,
    )
    config_entry.add_to_hass(hass)

    with (
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
        patch(
            "homeassistant.components.lifx.config_flow.find_by_ip",
            return_value=mock_light,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_homekit_info(),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == IP_ADDRESS
    mock_reload.assert_called_once_with(config_entry.entry_id)
    config_entry.mock_state(hass, config_entries.ConfigEntryState.NOT_LOADED)


async def test_ip_discovery_aborts_for_matching_flow(hass: HomeAssistant) -> None:
    """Test IP-only discovery does not duplicate an in-progress flow."""
    with (
        patch.object(
            hass.config_entries.flow,
            "async_has_matching_flow",
            return_value=True,
        ),
        patch(
            "homeassistant.components.lifx.config_flow.find_by_ip",
            side_effect=AssertionError("A matching flow must not connect again"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_homekit_info(),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_ip_discovery_aborts_when_device_is_missing(
    hass: HomeAssistant,
) -> None:
    """Test IP-only discovery aborts when the device cannot be identified."""
    with patch(
        "homeassistant.components.lifx.config_flow.find_by_ip",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HOMEKIT},
            data=_homekit_info(),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


def test_flow_matching_uses_host() -> None:
    """Test unidentified flows match by their target host."""
    flow = LIFXConfigFlow()
    other_flow = LIFXConfigFlow()
    flow.host = IP_ADDRESS
    other_flow.host = IP_ADDRESS

    assert flow.is_matching(other_flow)


@pytest.mark.parametrize(("source", "data"), DISCOVERY_SOURCES)
async def test_discovery_does_not_match_shared_legacy_entry(
    hass: HomeAssistant,
    mock_light: Light,
    source: str,
    data: DiscoveryData,
) -> None:
    """Test discovery never treats the shared legacy entry as one device."""
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=DOMAIN,
        version=1,
    )
    legacy_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.lifx.config_flow.Device.connect",
            return_value=mock_light,
        ),
        patch(
            "homeassistant.components.lifx.config_flow.find_by_ip",
            return_value=mock_light,
        ),
        patch(
            "homeassistant.components.lifx.config_flow.mac_candidates_for_serial",
            return_value=(SERIAL, "d0:73:d5:dd:ee:cd"),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


@pytest.mark.parametrize(("source", "data"), DISCOVERY_SOURCES)
async def test_discovery_with_unchanged_host_does_not_reload(
    hass: HomeAssistant,
    mock_light: Light,
    source: str,
    data: DiscoveryData,
) -> None:
    """Test discovery of an unchanged address does not reload a loaded entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL},
        unique_id=SERIAL,
        version=2,
        state=config_entries.ConfigEntryState.LOADED,
    )
    config_entry.add_to_hass(hass)

    with (
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
        patch(
            "homeassistant.components.lifx.config_flow.find_by_ip",
            return_value=mock_light,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_reload.assert_not_called()
    config_entry.mock_state(hass, config_entries.ConfigEntryState.NOT_LOADED)


@pytest.mark.parametrize(
    "info",
    [
        pytest.param(_zeroconf_info_without_serial(), id="missing"),
        pytest.param(_zeroconf_info(serial="not-a-serial"), id="invalid"),
    ],
)
async def test_zeroconf_without_valid_serial_falls_back_to_ip(
    hass: HomeAssistant, mock_light: Light, info: ZeroconfServiceInfo
) -> None:
    """Test invalid mDNS identity falls back to targeted IP identification."""
    with patch(
        "homeassistant.components.lifx.config_flow.find_by_ip",
        return_value=mock_light,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=info,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


@pytest.mark.parametrize(
    ("source", "data", "connect_error", "find_error"),
    [
        pytest.param(
            config_entries.SOURCE_INTEGRATION_DISCOVERY,
            {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL},
            None,
            AssertionError("Serial discovery must not probe by IP"),
            id="broadcast",
        ),
        pytest.param(
            config_entries.SOURCE_DHCP,
            _dhcp_info(),
            AssertionError("IP-only discovery must not connect with a serial"),
            None,
            id="dhcp",
        ),
        pytest.param(
            config_entries.SOURCE_HOMEKIT,
            _homekit_info(),
            AssertionError("IP-only discovery must not connect with a serial"),
            None,
            id="homekit",
        ),
    ],
)
async def test_discovery_source_creates_version_2_entry(
    hass: HomeAssistant,
    mock_light: Light,
    source: str,
    data: DiscoveryData,
    connect_error: Exception | None,
    find_error: Exception | None,
) -> None:
    """Test each non-mDNS discovery source creates a version 2 entry."""
    with (
        patch(
            "homeassistant.components.lifx.config_flow.Device.connect",
            return_value=mock_light,
            side_effect=connect_error,
        ),
        patch(
            "homeassistant.components.lifx.config_flow.find_by_ip",
            return_value=mock_light,
            side_effect=find_error,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=data
        )

    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL}
    assert result["result"].unique_id == SERIAL
    assert result["result"].version == 2


async def test_reconfigure_updates_the_host(
    hass: HomeAssistant, mock_light: Light
) -> None:
    """Test reconfiguring an entry points it at a new address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=SERIAL,
        data={CONF_HOST: OLD_IP_ADDRESS, CONF_SERIAL: SERIAL},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.lifx.config_flow.find_by_ip",
        return_value=mock_light,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL}


async def test_reconfigure_rejects_a_different_device(
    hass: HomeAssistant, mock_light: Light
) -> None:
    """Test an address that now answers for another device is refused."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="d073d5aabbcc",
        data={CONF_HOST: OLD_IP_ADDRESS, CONF_SERIAL: "d073d5aabbcc"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "homeassistant.components.lifx.config_flow.find_by_ip",
        return_value=mock_light,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert entry.data == {CONF_HOST: OLD_IP_ADDRESS, CONF_SERIAL: "d073d5aabbcc"}


async def test_reconfigure_with_an_unreachable_host(hass: HomeAssistant) -> None:
    """Test an address nothing answers at returns to the form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id=SERIAL,
        data={CONF_HOST: OLD_IP_ADDRESS, CONF_SERIAL: SERIAL},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "homeassistant.components.lifx.config_flow.find_by_ip", return_value=None
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data == {CONF_HOST: OLD_IP_ADDRESS, CONF_SERIAL: SERIAL}


async def test_manual_host_creates_version_2_entry(
    hass: HomeAssistant, mock_light: Light
) -> None:
    """Test manual host setup uses targeted identification."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.lifx.config_flow.find_by_ip",
        return_value=mock_light,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == LABEL
    assert result["data"] == {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL}
    assert result["result"].unique_id == SERIAL
    assert result["result"].version == 2


async def test_manual_hostname_is_stored_as_an_address(
    hass: HomeAssistant, mock_light: Light
) -> None:
    """Test a hostname is resolved before the entry records where to reach it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with (
        patch(
            "homeassistant.components.lifx.config_flow.find_by_ip",
            return_value=mock_light,
        ) as find_by_ip,
        patch(
            "homeassistant.components.lifx.util.gethostbyname",
            return_value=IP_ADDRESS,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "lifx.example.com"}
        )

    find_by_ip.assert_awaited_once_with(IP_ADDRESS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL}


@pytest.mark.parametrize(
    "entered_serial",
    [
        pytest.param(SERIAL, id="raw"),
        pytest.param(LEGACY_SERIAL, id="colon-separated"),
        pytest.param(SERIAL.upper(), id="upper-case"),
    ],
)
async def test_manual_serial_creates_version_2_entry(
    hass: HomeAssistant, mock_light: Light, entered_serial: str
) -> None:
    """Test manual serial setup broadcasts for the device that owns the serial."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.lifx.config_flow.find_by_serial",
        return_value=mock_light,
    ) as find_by_serial:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL: entered_serial}
        )

    find_by_serial.assert_awaited_once_with(SERIAL)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == LABEL
    assert result["data"] == {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL}
    assert result["result"].unique_id == SERIAL
    assert result["result"].version == 2


async def test_manual_serial_that_answers_no_broadcast(
    hass: HomeAssistant,
) -> None:
    """Test a serial no device answers for returns to the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.lifx.config_flow.find_by_serial",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL: SERIAL}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_manual_host_and_serial_connects_directly(
    hass: HomeAssistant, mock_light: Light
) -> None:
    """Test giving both identifiers skips discovery entirely."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with (
        patch(
            "homeassistant.components.lifx.config_flow.Device.connect",
            return_value=mock_light,
        ) as connect,
        patch("homeassistant.components.lifx.config_flow.find_by_ip") as find_by_ip,
        patch(
            "homeassistant.components.lifx.config_flow.find_by_serial"
        ) as find_by_serial,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS, CONF_SERIAL: LEGACY_SERIAL}
        )

    connect.assert_awaited_once_with(ip=IP_ADDRESS, serial=SERIAL)
    find_by_ip.assert_not_called()
    find_by_serial.assert_not_called()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL}
    assert result["result"].unique_id == SERIAL


async def test_manual_setup_rejects_a_malformed_serial(hass: HomeAssistant) -> None:
    """Test the manual step reports a serial it cannot act on."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SERIAL: "not-a-serial"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_SERIAL: "invalid_serial"}


async def test_manual_host_while_discovery_is_pending(
    hass: HomeAssistant, mock_light: Light
) -> None:
    """Test a manual add wins over a discovery flow parked on its confirm form."""
    with patch(
        "homeassistant.components.lifx.config_flow.Device.connect",
        return_value=mock_light,
    ):
        discovery = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL},
        )
    assert discovery["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.lifx.config_flow.find_by_ip",
        return_value=mock_light,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL}


@pytest.mark.parametrize(
    "find_error",
    [
        pytest.param(None, id="not-found"),
        pytest.param(LifxUnsupportedDeviceError(), id="unsupported"),
        pytest.param(OSError(), id="network-error"),
    ],
)
async def test_manual_host_cannot_connect(
    hass: HomeAssistant,
    mock_light: Light,
    find_error: Exception | None,
) -> None:
    """Test manual setup reports cannot-connect and recovers on a retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    find_by_ip = AsyncMock(return_value=None, side_effect=find_error)
    with patch("homeassistant.components.lifx.config_flow.find_by_ip", find_by_ip):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.lifx.config_flow.find_by_ip",
        return_value=mock_light,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL}


@pytest.mark.parametrize(
    "mutate_device",
    [
        pytest.param(_remove_light_state, id="missing-state"),
        pytest.param(_fail_light_refresh, id="refresh-error"),
    ],
)
async def test_manual_host_cannot_read_device_state(
    hass: HomeAssistant,
    mock_light: Light,
    mutate_device: DeviceMutator,
) -> None:
    """Test manual setup rejects a device whose state cannot be read."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mutate_device(mock_light)

    with patch(
        "homeassistant.components.lifx.config_flow.find_by_ip",
        return_value=mock_light,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: IP_ADDRESS}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
    mock_light.close.assert_awaited_once_with()


async def test_pick_broadcast_discovered_device(
    hass: HomeAssistant, mock_light: Light
) -> None:
    """Test selecting a metadata-only broadcast discovery result."""
    discovered = DiscoveredDevice(serial=SERIAL, ip=IP_ADDRESS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _mock_broadcast_discovery(discovered):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_device"

    with patch(
        "homeassistant.components.lifx.config_flow.Device.connect",
        return_value=mock_light,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: SERIAL}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL}


async def test_pick_device_without_discovery_results(hass: HomeAssistant) -> None:
    """Test the picker aborts when broadcast discovery is empty."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _mock_broadcast_discovery():
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_pick_device_cannot_validate_discovery(
    hass: HomeAssistant,
) -> None:
    """Test a disappeared broadcast result aborts cleanly."""
    discovered = DiscoveredDevice(serial=SERIAL, ip=IP_ADDRESS)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with _mock_broadcast_discovery(discovered):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    with patch(
        "homeassistant.components.lifx.config_flow.Device.connect",
        side_effect=LifxDeviceNotFoundError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: SERIAL}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
