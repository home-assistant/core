"""Tests for the Openhome config flow module."""

from homeassistant import data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.openhome.const import DOMAIN
from homeassistant.components.ssdp import ATTR_UPNP_FRIENDLY_NAME, ATTR_UPNP_UDN
from homeassistant.config_entries import SOURCE_SSDP
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_UDN = "uuid:4c494e4e-1234-ab12-abcd-01234567819f"
MOCK_FRIENDLY_NAME = "Test Client"
MOCK_SSDP_LOCATION = "http://device:12345/description.xml"

MOCK_DISCOVER = ssdp.SsdpServiceInfo(
    ssdp_usn="usn",
    ssdp_st="st",
    ssdp_location=MOCK_SSDP_LOCATION,
    upnp={ATTR_UPNP_FRIENDLY_NAME: MOCK_FRIENDLY_NAME, ATTR_UPNP_UDN: MOCK_UDN},
)


async def test_ssdp(hass: HomeAssistant) -> None:
    """Test a ssdp import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=MOCK_DISCOVER,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {CONF_NAME: MOCK_FRIENDLY_NAME}

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["title"] == MOCK_FRIENDLY_NAME
    assert result2["data"] == {CONF_HOST: MOCK_SSDP_LOCATION}


async def test_device_exists(hass: HomeAssistant) -> None:
    """Test a ssdp import where device already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_SSDP_LOCATION},
        title=MOCK_FRIENDLY_NAME,
        unique_id=MOCK_UDN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=MOCK_DISCOVER,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_missing_udn(hass: HomeAssistant) -> None:
    """Test a ssdp import where discovery is missing udn."""
    broken_discovery = ssdp.SsdpServiceInfo(
        ssdp_usn="usn",
        ssdp_st="st",
        ssdp_location=MOCK_SSDP_LOCATION,
        upnp={
            ATTR_UPNP_FRIENDLY_NAME: MOCK_FRIENDLY_NAME,
        },
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=broken_discovery,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "incomplete_discovery"


async def test_missing_ssdp_location(hass: HomeAssistant) -> None:
    """Test a ssdp import where discovery is missing udn."""
    broken_discovery = ssdp.SsdpServiceInfo(
        ssdp_usn="usn",
        ssdp_st="st",
        ssdp_location="",
        upnp={ATTR_UPNP_FRIENDLY_NAME: MOCK_FRIENDLY_NAME, ATTR_UPNP_UDN: MOCK_UDN},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=broken_discovery,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "incomplete_discovery"


async def test_host_updated(hass: HomeAssistant) -> None:
    """Test a ssdp import flow where host changes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "old_host"},
        title=MOCK_FRIENDLY_NAME,
        unique_id=MOCK_UDN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=MOCK_DISCOVER,
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data[CONF_HOST] == MOCK_SSDP_LOCATION
