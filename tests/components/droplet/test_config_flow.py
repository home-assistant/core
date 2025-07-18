"""Test Droplet config flow."""

from ipaddress import IPv4Address

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import MockClientBehaviors, mock_try_connect

from tests.common import MockConfigEntry


async def test_user_setup(hass: HomeAssistant) -> None:
    """Test Droplet user setup."""
    result = await hass.config_entries.flow.async_init(
        "droplet", context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "not_supported"


async def test_zeroconf_setup(hass: HomeAssistant) -> None:
    """Test successful setup of Droplet via zeroconf."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=IPv4Address("192.168.1.54"),
        ip_addresses=[IPv4Address("192.168.1.54")],
        port=443,
        hostname="Droplet-1234",
        type="_droplet._tcp.local.",
        name="Droplet-1234",
        properties={
            "manufacturer": "Hydrific, part of LIXIL",
            "model": "Droplet 1.0",
            "sw": "1.0.0",
            "sn": "F467",
        },
    )
    result = await hass.config_entries.flow.async_init(
        "droplet",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result is not None
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "confirm"

    with mock_try_connect(MockClientBehaviors.GOOD):
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"), user_input={"pairing_code": "12223"}
        )
    await hass.async_block_till_done()
    assert result is not None
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {
        "device_id": "Droplet-1234",
        "droplet_host": "192.168.1.54",
        "droplet_port": 443,
        "manufacturer": "Hydrific, part of LIXIL",
        "model": "Droplet 1.0",
        "name": "Droplet",
        "pairing_code": "12223",
        "sn": "F467",
        "sw": "1.0.0",
    }


async def test_zeroconf_update(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test updating Droplet's host with zeroconf."""
    mock_config_entry.add_to_hass(hass)

    # We start with a different host
    new_host = "192.168.1.5"
    entries = hass.config_entries.async_entries("droplet")
    assert entries[0].data.get("droplet_host") != new_host

    # After this discovery message, host should be updated
    discovery_info = ZeroconfServiceInfo(
        ip_address=IPv4Address(new_host),
        ip_addresses=[IPv4Address(new_host)],
        port=443,
        hostname="Droplet-1234",
        type="_droplet._tcp.local.",
        name="Droplet-1234",
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        "droplet",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result is not None
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"

    entries = hass.config_entries.async_entries("droplet")
    assert entries[0].data.get("droplet_host") == new_host


async def test_zeroconf_invalid_discovery(hass: HomeAssistant) -> None:
    """Test that invalid discovery information causes the config flow to abort."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=IPv4Address("192.168.1.2"),
        ip_addresses=[IPv4Address("192.168.1.2")],
        port=-1,
        hostname="Droplet-1234",
        type="_droplet._tcp.local.",
        name="Droplet-1234",
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        "droplet",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result is not None
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_discovery_info"


async def test_confirm_failed_connect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that config flow fails with Droplet can't connect."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=IPv4Address("192.168.1.2"),
        ip_addresses=[IPv4Address("192.168.1.2")],
        port=443,
        hostname="Droplet-1234",
        type="_droplet._tcp.local.",
        name="Droplet-1234",
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        "droplet",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result.get("type") == FlowResultType.FORM

    with mock_try_connect(MockClientBehaviors.FAIL_OPEN):
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"), user_input={"pairing_code": "12223"}
        )
        await hass.async_block_till_done()
        assert result is not None
        assert result.get("type") == FlowResultType.FORM
        errors = result.get("errors")
        assert errors
        assert errors.get("base") == "failed_connect"
