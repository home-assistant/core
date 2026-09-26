"""Tests for the LibreSync config flow."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from aiolibresync import DiscoveredDevice
import pytest

from homeassistant.components.libresync.const import CONF_SERIAL, CONF_UDN, DOMAIN
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_SSDP,
    SOURCE_USER,
    ConfigEntryState,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .conftest import FOUND, HOST, SERIAL, UDN

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

SSDP_INFO = SsdpServiceInfo(
    ssdp_usn=f"{UDN}::urn:schemas-upnp-org:device:MediaRenderer:1",
    ssdp_st="urn:schemas-upnp-org:device:MediaRenderer:1",
    ssdp_location=f"http://{HOST}:38400/description.xml",
    upnp={"UDN": UDN, "manufacturer": "LibreWireless", "friendlyName": "Stereo"},
)


def _ssdp(location: str) -> SsdpServiceInfo:
    return replace(SSDP_INFO, ssdp_location=location)


@pytest.mark.usefixtures("mock_probe", "mock_read_serial")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test adding a hub by address, keyed on its serial."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Stereo"
    assert result["result"].unique_id == SERIAL
    assert result["data"] == {CONF_HOST: HOST, CONF_SERIAL: SERIAL, CONF_UDN: UDN}


@pytest.mark.usefixtures("mock_probe")
async def test_user_flow_without_serial(
    hass: HomeAssistant, mock_read_serial: AsyncMock
) -> None:
    """Test a hub with no valid factory serial is keyed on its UDN."""
    mock_read_serial.return_value = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UDN
    assert result["data"] == {CONF_HOST: HOST, CONF_UDN: UDN}


@pytest.mark.usefixtures("mock_read_serial")
async def test_user_flow_without_udn(
    hass: HomeAssistant, mock_probe: AsyncMock
) -> None:
    """Test a hub whose UPnP daemon is down is keyed on its serial."""
    mock_probe.return_value = DiscoveredDevice(host=HOST, udn=None)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LibreSync hub"
    assert result["result"].unique_id == SERIAL
    assert result["data"] == {CONF_HOST: HOST, CONF_SERIAL: SERIAL}


@pytest.mark.usefixtures("mock_read_serial")
async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_probe: AsyncMock
) -> None:
    """Test a host that does not answer, and the recovery."""
    mock_probe.return_value = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_probe.return_value = FOUND
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_no_identity(
    hass: HomeAssistant, mock_probe: AsyncMock, mock_read_serial: AsyncMock
) -> None:
    """Test a hub with neither serial nor UDN is refused, and the recovery."""
    mock_probe.return_value = DiscoveredDevice(host=HOST, udn=None)
    mock_read_serial.return_value = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_identity"}

    mock_probe.return_value = FOUND
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UDN


@pytest.mark.usefixtures("mock_probe")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_read_serial: AsyncMock,
) -> None:
    """Test the same hub cannot be added twice, and is not asked for its serial."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_read_serial.assert_not_awaited()


@pytest.mark.usefixtures("mock_probe")
async def test_user_flow_recognises_udn_entry(
    hass: HomeAssistant, mock_read_serial: AsyncMock
) -> None:
    """Test an entry keyed on the UDN is recognised without reading the serial."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=UDN, data={CONF_HOST: HOST, CONF_UDN: UDN}
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == UDN
    assert CONF_SERIAL not in entry.data
    mock_read_serial.assert_not_awaited()


@pytest.mark.usefixtures("mock_probe_control", "mock_read_serial")
async def test_ssdp_flow(hass: HomeAssistant) -> None:
    """Test a discovered hub is confirmed and keyed on its serial."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Stereo"
    assert result["result"].unique_id == SERIAL
    assert result["data"] == {CONF_HOST: HOST, CONF_SERIAL: SERIAL, CONF_UDN: UDN}


@pytest.mark.usefixtures("mock_read_serial")
async def test_ssdp_already_in_progress(
    hass: HomeAssistant, mock_probe_control: AsyncMock
) -> None:
    """Test a second discovery of a hub being set up is dropped unprobed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_INFO
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=replace(SSDP_INFO, ssdp_st="upnp:rootdevice"),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
    mock_probe_control.assert_awaited_once()


async def test_ssdp_known_hub_moved(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_probe_control: AsyncMock,
    mock_read_serial: AsyncMock,
) -> None:
    """Test a known hub is followed to its new address without being contacted."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=_ssdp("http://192.168.1.99:38400/description.xml"),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.99"
    mock_probe_control.assert_not_awaited()
    mock_read_serial.assert_not_awaited()


@pytest.mark.parametrize(
    ("state", "reloaded"),
    [
        (ConfigEntryState.SETUP_RETRY, True),
        (ConfigEntryState.LOADED, False),
    ],
)
async def test_ssdp_known_hub_reloads_when_retrying(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    state: ConfigEntryState,
    reloaded: bool,
) -> None:
    """Test a hub found again at the same address retries a waiting setup."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, state)
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_INFO
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert reload.called is reloaded


@pytest.mark.usefixtures("mock_probe_control", "mock_read_serial")
async def test_ssdp_learns_udn_of_serial_entry(hass: HomeAssistant) -> None:
    """Test an entry added while its UPnP daemon was down learns its UDN."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=SERIAL, data={CONF_HOST: HOST, CONF_SERIAL: SERIAL}
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_UDN] == UDN


@pytest.mark.usefixtures("mock_read_serial")
@pytest.mark.parametrize(
    "discovery",
    [
        _ssdp("http:///description.xml"),
        replace(SSDP_INFO, ssdp_usn="", upnp={"manufacturer": "LibreWireless"}),
    ],
    ids=["no_host", "no_udn"],
)
async def test_ssdp_unusable(
    hass: HomeAssistant, mock_probe_control: AsyncMock, discovery: SsdpServiceInfo
) -> None:
    """Test a discovery with no host or no UDN is dropped."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    mock_probe_control.assert_not_awaited()


@pytest.mark.usefixtures("mock_read_serial")
async def test_ssdp_not_a_hub(
    hass: HomeAssistant, mock_probe_control: AsyncMock
) -> None:
    """Test a renderer that does not answer on the control port is dropped."""
    mock_probe_control.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_ignored_hub_not_contacted(
    hass: HomeAssistant, mock_probe_control: AsyncMock, mock_read_serial: AsyncMock
) -> None:
    """Test a hub the user ignored is dropped before anything is sent to it."""
    MockConfigEntry(domain=DOMAIN, source=SOURCE_IGNORE, unique_id=UDN).add_to_hass(
        hass
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_probe_control.assert_not_awaited()
    mock_read_serial.assert_not_awaited()


@pytest.mark.usefixtures("mock_probe_control", "mock_probe", "mock_read_serial")
async def test_ssdp_confirm_after_manual_add(hass: HomeAssistant) -> None:
    """Test confirming a discovery of a hub added by address meanwhile aborts."""
    discovered = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_INFO
    )
    assert discovered["type"] is FlowResultType.FORM

    manual = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    manual = await hass.config_entries.flow.async_configure(
        manual["flow_id"], {CONF_HOST: HOST}
    )
    assert manual["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_configure(discovered["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_probe", "mock_read_serial")
async def test_user_flow_replaces_ignored_discovery(hass: HomeAssistant) -> None:
    """Test a hub ignored under its UDN is no longer ignored once added by hand."""
    MockConfigEntry(domain=DOMAIN, source=SOURCE_IGNORE, unique_id=UDN).add_to_hass(
        hass
    )
    other = MockConfigEntry(
        domain=DOMAIN, source=SOURCE_IGNORE, unique_id="uuid:another-hub"
    )
    other.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert {
        (entry.source, entry.unique_id)
        for entry in hass.config_entries.async_entries(DOMAIN)
    } == {(SOURCE_IGNORE, "uuid:another-hub"), (SOURCE_USER, SERIAL)}
