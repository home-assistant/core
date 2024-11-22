"""Tests for the BSBLan device config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, Mock

from bsblan import BSBLANConnectionError

from homeassistant.components.bsblan import config_flow
from homeassistant.components.bsblan.const import CONF_PASSKEY, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry


async def test_full_user_flow_implementation(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == format_mac("00:80:41:19:69:90")
    assert result2.get("data") == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 80,
        CONF_PASSKEY: "1234",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "admin1234",
    }
    assert "result" in result2
    assert result2["result"].unique_id == format_mac("00:80:41:19:69:90")

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_bsblan.device.mock_calls) == 1


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM


async def test_connection_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test we show user form on BSBLan connection error."""
    mock_bsblan.device.side_effect = BSBLANConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}
    assert result.get("step_id") == "user"


async def test_user_device_exists_abort(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort flow if BSBLAN device already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_zeroconf_discovery(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the Zeroconf discovery flow."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("10.0.2.60"),
        ip_addresses=[ip_address("10.0.2.60")],
        name="BSB-LAN web service._http._tcp.local.",
        type="_http._tcp.local.",
        properties={"mac": "00:80:41:19:69:90"},  # Include MAC address
        port=80,
        hostname="BSB-LAN.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "discovery_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == format_mac("00:80:41:19:69:90")
    assert result2.get("data") == {
        CONF_HOST: "10.0.2.60",
        CONF_PORT: 80,
        CONF_PASSKEY: "1234",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "admin1234",
    }
    assert "result" in result2
    assert result2["result"].unique_id == format_mac("00:80:41:19:69:90")

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_bsblan.device.mock_calls) == 1


async def test_abort_if_existing_entry_for_zeroconf(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test we abort if the same host/port already exists during zeroconf discovery."""
    # Create an existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        unique_id="00:80:41:19:69:90",
    )
    entry.add_to_hass(hass)

    # Mock zeroconf discovery of the same device
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("10.0.2.60"),
        ip_addresses=[ip_address("10.0.2.60")],
        name="BSB-LAN web service._http._tcp.local.",
        type="_http._tcp.local.",
        properties={"mac": "00:80:41:19:69:90"},  # Include MAC address
        port=80,
        hostname="BSB-LAN.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_discovery_mac_from_properties_raw(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test Zeroconf discovery when MAC is found in properties_raw instead of properties."""
    # Create a mock object that mimics ZeroconfServiceInfo but allows properties_raw
    discovery_info = Mock()
    discovery_info.ip_address = ip_address("10.0.2.60")
    discovery_info.ip_addresses = [ip_address("10.0.2.60")]
    discovery_info.name = "BSB-LAN web service._http._tcp.local."
    discovery_info.type = "_http._tcp.local."
    discovery_info.properties = {}  # No MAC in properties
    discovery_info.properties_raw = {
        b"mac=00:80:41:19:69:90": b""
    }  # MAC in properties_raw
    discovery_info.port = 80
    discovery_info.hostname = "BSB-LAN.local."

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "discovery_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == format_mac("00:80:41:19:69:90")
    assert result2.get("data") == {
        CONF_HOST: "10.0.2.60",
        CONF_PORT: 80,
        CONF_PASSKEY: "1234",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "admin1234",
    }
    assert "result" in result2
    assert result2["result"].unique_id == format_mac("00:80:41:19:69:90")

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_bsblan.device.mock_calls) == 1


async def test_zeroconf_discovery_no_mac_abort(
    hass: HomeAssistant,
) -> None:
    """Test Zeroconf discovery aborts when no MAC address is found."""
    # Create a mock object that mimics ZeroconfServiceInfo but allows properties_raw
    discovery_info = Mock()
    discovery_info.ip_address = ip_address("10.0.2.60")
    discovery_info.ip_addresses = [ip_address("10.0.2.60")]
    discovery_info.name = "BSB-LAN web service._http._tcp.local."
    discovery_info.type = "_http._tcp.local."
    discovery_info.properties = {}  # No MAC in properties
    discovery_info.properties_raw = {}  # No MAC in properties_raw either
    discovery_info.port = 80
    discovery_info.hostname = "BSB-LAN.local."

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_mac_address"
