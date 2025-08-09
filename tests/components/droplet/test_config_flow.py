"""Test Droplet config flow."""

from ipaddress import IPv4Address
from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import MockClientBehaviors, mock_try_connect

from tests.common import MockConfigEntry


async def test_user_setup(
    hass: HomeAssistant, mock_coordinator_setup: MagicMock
) -> None:
    """Test successful Droplet user setup."""
    result = await hass.config_entries.flow.async_init(
        "droplet", context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    with mock_try_connect(MockClientBehaviors.GOOD):
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"), user_input={"code": "123456", "host": "192.168.1.2"}
        )
        assert result is not None
        assert result.get("type") is FlowResultType.CREATE_ENTRY
        assert result.get("data") == {
            "code": "123456",
            "device_id": "Droplet-1234",
            "host": "192.168.1.2",
            "name": "Droplet",
            "port": 443,
        }


async def test_user_setup_failed_connect(hass: HomeAssistant) -> None:
    """Test user setup when the device fails to connect at all."""
    result = await hass.config_entries.flow.async_init(
        "droplet", context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    with mock_try_connect(MockClientBehaviors.FAIL_OPEN):
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"), user_input={"code": "123456", "host": "192.168.1.2"}
        )
        assert result is not None
        assert result.get("type") is FlowResultType.FORM
        assert result.get("errors") == {"base": "failed_connect"}


async def test_user_setup_no_device_id(hass: HomeAssistant) -> None:
    """Test user setup when the device connects but fails to send its ID."""
    result = await hass.config_entries.flow.async_init(
        "droplet", context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    with mock_try_connect(MockClientBehaviors.NO_DEVICE_ID):
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"), user_input={"code": "123456", "host": "192.168.1.2"}
        )
        assert result is not None
        assert result.get("type") is FlowResultType.FORM
        assert result.get("errors") == {"base": "failed_connect"}


async def test_user_setup_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user setup of an already-configured device."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "droplet", context={"source": config_entries.SOURCE_USER}
    )
    assert result is not None
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    with mock_try_connect(MockClientBehaviors.GOOD):
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"), user_input={"code": "123456", "host": "192.168.1.2"}
        )
        assert result is not None
        assert result.get("type") is FlowResultType.ABORT
        assert result.get("reason") == "already_configured"


async def test_zeroconf_setup(
    hass: HomeAssistant, mock_coordinator_setup: MagicMock
) -> None:
    """Test successful setup of Droplet via zeroconf."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=IPv4Address("192.168.1.54"),
        ip_addresses=[IPv4Address("192.168.1.54")],
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
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "confirm"

    with mock_try_connect(MockClientBehaviors.GOOD):
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"), user_input={"code": "12223"}
        )
    await hass.async_block_till_done()
    assert result is not None
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {
        "device_id": "Droplet-1234",
        "host": "192.168.1.54",
        "port": 443,
        "code": "12223",
        "name": "Droplet",
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
    assert entries[0].data.get("host") == new_host


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
    """Test that config flow fails when Droplet can't connect."""
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
            result.get("flow_id"), user_input={"code": "12223"}
        )
        await hass.async_block_till_done()
        assert result is not None
        assert result.get("type") == FlowResultType.FORM
        errors = result.get("errors")
        assert errors
        assert errors.get("base") == "failed_connect"
