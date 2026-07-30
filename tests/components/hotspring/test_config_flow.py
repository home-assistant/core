"""Tests for the Hot Spring config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

from hotspring import HotSpringConnectionError
import pytest

from homeassistant.components.hotspring.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry", "mock_hotspring")
async def test_full_user_flow_implementation(hass: HomeAssistant) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
    )

    assert result.get("title") == "ConnectedSpa_C59C9C"
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert "result" in result
    assert result["result"].unique_id == "AA:AA:AA:AA:AA:BB"


@pytest.mark.usefixtures("mock_hotspring")
async def test_user_device_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort the config flow if Hot Spring spa is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "192.168.1.100"},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_connection_error(hass: HomeAssistant, mock_hotspring: MagicMock) -> None:
    """Test we show user form on Hot Spring connection error."""
    mock_hotspring.update.side_effect = HotSpringConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "example.com"},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_setup_entry", "mock_hotspring")
async def test_full_user_flow_with_error(
    hass: HomeAssistant, mock_hotspring: MagicMock
) -> None:
    """Test the full manual user flow with some errors in the middle."""
    mock_hotspring.update.side_effect = HotSpringConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "cannot_connect"}

    mock_hotspring.update.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
    )

    assert result.get("title") == "ConnectedSpa_C59C9C"
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert "result" in result
    assert result["result"].unique_id == "AA:AA:AA:AA:AA:BB"


@pytest.mark.usefixtures("mock_setup_entry", "mock_hotspring")
async def test_full_zeroconf_flow_implementation(hass: HomeAssistant) -> None:
    """Test the full zeroconf flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="ConnectedSpa_C59C9C.local.",
            name="ConnectedSpa_C59C9C._ws._tcp.local.",
            port=80,
            properties={CONF_MAC: "AA:AA:AA:AA:AA:BB"},
            type="_ws._tcp.local.",
        ),
    )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    assert result.get("description_placeholders") == {CONF_NAME: "ConnectedSpa_C59C9C"}
    assert result.get("step_id") == "zeroconf_confirm"
    assert result.get("type") is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result2.get("title") == "ConnectedSpa_C59C9C"
    assert result2.get("type") is FlowResultType.CREATE_ENTRY

    assert "data" in result2
    assert result2["data"][CONF_HOST] == "192.168.1.100"
    assert "result" in result2
    assert result2["result"].unique_id == "AA:AA:AA:AA:AA:BB"


@pytest.mark.usefixtures("mock_hotspring")
async def test_zeroconf_during_onboarding(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_onboarding: MagicMock,
) -> None:
    """Test we create a config entry when discovered during onboarding."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="ConnectedSpa_C59C9C.local.",
            name="ConnectedSpa_C59C9C._ws._tcp.local.",
            port=80,
            properties={CONF_MAC: "AA:AA:AA:AA:AA:BB"},
            type="_ws._tcp.local.",
        ),
    )

    assert result.get("title") == "ConnectedSpa_C59C9C"
    assert result.get("type") is FlowResultType.CREATE_ENTRY

    assert result.get("data") == {CONF_HOST: "192.168.1.100"}
    assert "result" in result
    assert result["result"].unique_id == "AA:AA:AA:AA:AA:BB"

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1


async def test_zeroconf_connection_error(
    hass: HomeAssistant, mock_hotspring: MagicMock
) -> None:
    """Test we abort zeroconf flow on Hot Spring connection error."""
    mock_hotspring.update.side_effect = HotSpringConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="ConnectedSpa_C59C9C.local.",
            name="ConnectedSpa_C59C9C._ws._tcp.local.",
            port=80,
            properties={},
            type="_ws._tcp.local.",
        ),
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


async def test_zeroconf_with_mac_device_exists_abort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_hotspring: MagicMock
) -> None:
    """Test we abort zeroconf flow if Hot Spring spa already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="ConnectedSpa_C59C9C.local.",
            name="ConnectedSpa_C59C9C._ws._tcp.local.",
            port=80,
            properties={CONF_MAC: "AA:AA:AA:AA:AA:BB"},
            type="_ws._tcp.local.",
        ),
    )

    mock_hotspring.update.assert_not_called()
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("mock_hotspring")
async def test_zeroconf_without_mac_device_exists_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort zeroconf flow if Hot Spring spa already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.100"),
            ip_addresses=[ip_address("192.168.1.100")],
            hostname="ConnectedSpa_C59C9C.local.",
            name="ConnectedSpa_C59C9C._ws._tcp.local.",
            port=80,
            properties={},
            type="_ws._tcp.local.",
        ),
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test the full reconfigure flow from start to finish."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result.get("step_id") == "user"
    assert result.get("type") is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.200"}
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"

    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_reconfigure_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test reconfiguration failure when the unique ID changes."""
    mock_config_entry.add_to_hass(hass)

    # Change mac address to simulate a different device
    mock_hotspring.update.return_value.info.mac_address = "CC:CC:CC:CC:CC:DD"

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result.get("step_id") == "user"
    assert result.get("type") is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.200"}
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "unique_id_mismatch"
