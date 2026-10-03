"""Tests for the LibreSync config flow."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from aiolibresync import DiscoveredDevice
import pytest

from homeassistant.components.libresync.const import DOMAIN
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

from .conftest import FOUND, HOST, UDN

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

SSDP_INFO = SsdpServiceInfo(
    ssdp_usn=f"{UDN}::urn:schemas-upnp-org:device:MediaRenderer:1",
    ssdp_st="urn:schemas-upnp-org:device:MediaRenderer:1",
    ssdp_location=f"http://{HOST}:38400/description.xml",
    upnp={"UDN": UDN, "manufacturer": "LibreWireless", "friendlyName": "Stereo"},
)

NEW_HOST = "192.168.1.99"


def _ssdp(location: str) -> SsdpServiceInfo:
    return replace(SSDP_INFO, ssdp_location=location)


@pytest.mark.usefixtures("mock_probe")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test adding a hub by address, keyed on its UDN."""
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
    assert result["result"].unique_id == UDN
    assert result["data"] == {CONF_HOST: HOST}


@pytest.mark.parametrize(
    ("found", "error"),
    [
        pytest.param(None, "cannot_connect", id="cannot_connect"),
        # The control port answers, but the UPnP service does not.
        pytest.param(DiscoveredDevice(host=HOST, udn=None), "no_identity", id="no_udn"),
        # A description whose UDN element holds only whitespace.
        pytest.param(
            DiscoveredDevice(host=HOST, udn=""), "no_identity", id="empty_udn"
        ),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_probe: AsyncMock,
    found: DiscoveredDevice | None,
    error: str,
) -> None:
    """Test a hub that cannot be added, and the recovery."""
    mock_probe.return_value = found
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_probe.return_value = FOUND
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UDN


@pytest.mark.usefixtures("mock_probe")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same hub cannot be added twice, and its address is updated."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={CONF_HOST: NEW_HOST}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == HOST


@pytest.mark.usefixtures("mock_probe")
async def test_user_flow_replaces_ignored_discovery(hass: HomeAssistant) -> None:
    """Test a hub the user ignored can still be added by address."""
    MockConfigEntry(domain=DOMAIN, source=SOURCE_IGNORE, unique_id=UDN).add_to_hass(
        hass
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert [
        (entry.source, entry.unique_id)
        for entry in hass.config_entries.async_entries(DOMAIN)
    ] == [(SOURCE_USER, UDN)]


@pytest.mark.usefixtures("mock_probe_control")
async def test_ssdp_flow(hass: HomeAssistant) -> None:
    """Test a discovered hub is confirmed and keyed on its UDN."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Stereo"
    assert result["result"].unique_id == UDN
    assert result["data"] == {CONF_HOST: HOST}


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
) -> None:
    """Test a known hub is followed to its new address without being contacted."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=_ssdp(f"http://{NEW_HOST}:38400/description.xml"),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == NEW_HOST
    mock_probe_control.assert_not_awaited()


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
    hass: HomeAssistant, mock_probe_control: AsyncMock
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


@pytest.mark.usefixtures("mock_probe_control", "mock_probe")
async def test_ssdp_dropped_after_manual_add(hass: HomeAssistant) -> None:
    """Test a pending discovery of a hub added by address meanwhile goes away."""
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
    assert hass.config_entries.flow.async_progress() == []
