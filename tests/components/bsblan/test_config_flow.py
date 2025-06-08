"""Tests for the BSBLan device config flow."""

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
    zeroconf_discovery_info: ZeroconfServiceInfo,
) -> None:
    """Test the Zeroconf discovery flow."""
    discovery_info = zeroconf_discovery_info

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
    zeroconf_discovery_info: ZeroconfServiceInfo,
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
    discovery_info = zeroconf_discovery_info

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
    zeroconf_discovery_info_properties_raw: Mock,
) -> None:
    """Test Zeroconf discovery when MAC is found in properties_raw instead of properties."""
    # Create a mock object that mimics ZeroconfServiceInfo but allows properties_raw
    discovery_info = zeroconf_discovery_info_properties_raw

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


async def test_zeroconf_discovery_no_mac_in_announcement(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    zeroconf_discovery_info_no_mac: Mock,
) -> None:
    """Test Zeroconf discovery works when no MAC address is in the announcement."""
    # Create a mock object that mimics ZeroconfServiceInfo but allows properties_raw
    discovery_info = zeroconf_discovery_info_no_mac

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    # Now complete the discovery by providing credentials and connecting
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
        },
    )

    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "00:80:41:19:69:90"  # MAC from fixture file
    assert result2["data"] == {
        CONF_HOST: "10.0.2.60",
        CONF_PORT: 80,
        CONF_PASSKEY: None,
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "secret",
    }


async def test_zeroconf_discovery_connection_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    zeroconf_discovery_info: ZeroconfServiceInfo,
) -> None:
    """Test connection error during zeroconf discovery shows the correct form."""
    mock_bsblan.device.side_effect = BSBLANConnectionError

    discovery_info = zeroconf_discovery_info

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

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "discovery_confirm"
    assert result2.get("errors") == {"base": "cannot_connect"}


async def test_zeroconf_discovery_doesnt_update_host_port_on_existing_entry(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    zeroconf_discovery_info: ZeroconfServiceInfo,
) -> None:
    """Test that discovered devices don't update host/port of existing entries."""
    # Create an existing entry with different host/port
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",  # Different IP
            CONF_PORT: 8080,  # Different port
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        unique_id="00:80:41:19:69:90",
    )
    entry.add_to_hass(hass)

    # Mock zeroconf discovery of the same device but with different IP/port
    discovery_info = zeroconf_discovery_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # Should abort because device is already configured
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify the existing entry was NOT updated with new host/port
    assert entry.data[CONF_HOST] == "192.168.1.100"  # Original host preserved
    assert entry.data[CONF_PORT] == 8080  # Original port preserved


async def test_user_flow_can_update_existing_host_port(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test that manual user configuration can update host/port of existing entries."""
    # Create an existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 8080,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        unique_id="00:80:41:19:69:90",
    )
    entry.add_to_hass(hass)

    # Try to configure the same device with different host/port via user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "10.0.2.60",  # Different IP
            CONF_PORT: 80,  # Different port
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    # Should abort because device is already configured, but should update host/port
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify the existing entry WAS updated with new host/port (user flow behavior)
    assert entry.data[CONF_HOST] == "10.0.2.60"  # Updated host
    assert entry.data[CONF_PORT] == 80  # Updated port


async def test_zeroconf_discovery_mac_mismatch_updates_unique_id(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_setup_entry: AsyncMock,
    zeroconf_discovery_info_different_mac: ZeroconfServiceInfo,
) -> None:
    """Test Zeroconf discovery when MAC from discovery differs from device API."""
    # The fixture provides MAC "aa:bb:cc:dd:ee:ff" in Zeroconf discovery
    # But the mock device API returns "00:80:41:19:69:90" (from device.json)
    discovery_info = zeroconf_discovery_info_different_mac

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
    # Title should use the MAC from the device API, not from Zeroconf
    assert result2.get("title") == format_mac("00:80:41:19:69:90")
    assert result2.get("data") == {
        CONF_HOST: "10.0.2.60",
        CONF_PORT: 80,
        CONF_PASSKEY: "1234",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "admin1234",
    }
    assert "result" in result2
    # Unique ID should be updated to the MAC from device API
    assert result2["result"].unique_id == format_mac("00:80:41:19:69:90")

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_bsblan.device.mock_calls) == 1
