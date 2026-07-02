"""Tests for the PowerShades config flow."""

from unittest.mock import patch

from pyowershades import PowerShadesTimeoutError

from homeassistant.components.powershades.config_flow import MANUAL_ENTRY
from homeassistant.components.powershades.const import DOMAIN
from homeassistant.config_entries import (
    SOURCE_DHCP,
    SOURCE_INTEGRATION_DISCOVERY,
    SOURCE_USER,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

TEST_IP = "192.168.1.50"


async def test_manual_flow_success(
    hass: HomeAssistant, mock_discover_devices, mock_device_info, mock_setup_entry
) -> None:
    """No devices discovered, user enters an IP manually and it works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip": TEST_IP}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "PowerShade Bedroom Shade"
    assert result["data"] == {
        "ip": TEST_IP,
        "serial": 12345,
        "name": "Bedroom Shade",
        "model": 1,
    }


async def test_manual_flow_cannot_connect(
    hass: HomeAssistant, mock_discover_devices
) -> None:
    """The device does not respond to the probe."""
    with patch(
        "homeassistant.components.powershades.config_flow.async_get_device_info",
        side_effect=PowerShadesTimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"ip": TEST_IP}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_manual_flow_invalid_ip(
    hass: HomeAssistant, mock_discover_devices
) -> None:
    """An invalid IPv4 address is rejected before probing the device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip": "not-an-ip"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"ip": "invalid_ip"}


async def test_manual_flow_duplicate(
    hass: HomeAssistant, mock_discover_devices, mock_device_info
) -> None:
    """A shade that's already configured (by serial) cannot be added again."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip": TEST_IP, "serial": 12345, "name": "Bedroom Shade", "model": 1},
        unique_id="12345",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip": TEST_IP}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_pick_device(
    hass: HomeAssistant, mock_device_info, mock_setup_entry
) -> None:
    """Discovered devices are offered for selection."""
    with patch(
        "homeassistant.components.powershades.config_flow.async_discover_devices",
        return_value=[{"ip": TEST_IP, "serial": 12345, "model": 1}],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pick_device"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": TEST_IP}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "PowerShade Bedroom Shade"
    assert result["data"]["ip"] == TEST_IP
    assert result["data"]["serial"] == 12345


async def test_discovery_hides_already_configured_devices(
    hass: HomeAssistant, mock_device_info, mock_setup_entry
) -> None:
    """Devices that already have a config entry are not offered again."""
    configured = MockConfigEntry(
        domain=DOMAIN,
        data={"ip": TEST_IP, "serial": 12345, "name": "Bedroom Shade", "model": 1},
        unique_id="12345",
    )
    configured.add_to_hass(hass)

    new_ip = "192.168.1.51"
    with patch(
        "homeassistant.components.powershades.config_flow.async_discover_devices",
        return_value=[
            {"ip": TEST_IP, "serial": 12345, "model": 1},
            {"ip": new_ip, "serial": 67890, "model": 1},
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_device"
    assert new_ip in result["data_schema"].schema["device"].container
    assert TEST_IP not in result["data_schema"].schema["device"].container


async def test_pick_device_manual_entry(
    hass: HomeAssistant, mock_device_info, mock_setup_entry
) -> None:
    """Choosing manual entry from the discovered-device list goes to the manual step."""
    with patch(
        "homeassistant.components.powershades.config_flow.async_discover_devices",
        return_value=[{"ip": TEST_IP, "serial": 12345, "model": 1}],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "pick_device"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": MANUAL_ENTRY}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_dhcp_discovery_cannot_connect(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """A DHCP-discovered device that doesn't respond to a probe aborts."""
    discovery_info = DhcpServiceInfo(
        ip=TEST_IP,
        hostname="ps-bedroom",
        macaddress="d83af5112233",
    )

    with patch(
        "homeassistant.components.powershades.config_flow.async_get_device_info",
        side_effect=PowerShadesTimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_DHCP}, data=discovery_info
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_integration_discovery_probes_for_name(
    hass: HomeAssistant, mock_device_info, mock_setup_entry
) -> None:
    """Background discovery without a name probes the device for one."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={"ip": TEST_IP, "serial": 12345},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["name"] == "Bedroom Shade"
    assert result["data"]["model"] == 1


async def test_integration_discovery_probe_timeout(
    hass: HomeAssistant, mock_setup_entry
) -> None:
    """If probing for the name times out, discovery continues without one."""
    with patch(
        "homeassistant.components.powershades.config_flow.async_get_device_info",
        side_effect=PowerShadesTimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data={"ip": TEST_IP, "serial": 12345, "model": 1},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"]["name"] == "PowerShades device"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["name"] is None


async def test_dhcp_discovery(
    hass: HomeAssistant, mock_device_info, mock_setup_entry
) -> None:
    """A device found via DHCP is confirmed and added."""
    discovery_info = DhcpServiceInfo(
        ip=TEST_IP,
        hostname="ps-bedroom",
        macaddress="d83af5112233",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=discovery_info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "PowerShade Bedroom Shade"
    assert result["data"] == {
        "ip": TEST_IP,
        "serial": 12345,
        "name": "Bedroom Shade",
        "mac": "d8:3a:f5:11:22:33",
        "model": 1,
    }


async def test_background_discovery_already_configured(
    hass: HomeAssistant, mock_device_info, mock_setup_entry
) -> None:
    """Background discovery of an already-configured device aborts."""
    configured = MockConfigEntry(
        domain=DOMAIN,
        data={"ip": TEST_IP, "serial": 12345, "name": "Bedroom Shade", "model": 1},
        unique_id="12345",
    )
    configured.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={"ip": TEST_IP, "serial": 12345, "model": 1},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
