"""Tests for the WiiM config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from async_upnp_client.exceptions import UpnpConnectionError
import pytest

from homeassistant.components.wiim.config_flow import (
    CannotConnect,
    WiimConfigFlow,
    _validate_device_and_get_info,
)
from homeassistant.components.wiim.const import CONF_UDN, CONF_UPNP_LOCATION
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant


@pytest.fixture
def flow(mock_hass: HomeAssistant):
    """Fixture for a WiimConfigFlow instance."""
    return WiimConfigFlow(), mock_hass


@pytest.mark.asyncio
async def test_async_step_user_success(mock_hass: HomeAssistant) -> None:
    """Test user step returns entry on successful device validation."""

    mock_device_info = {
        CONF_HOST: "192.168.1.100",
        CONF_UDN: "uuid:test-1234",
        CONF_NAME: "WiiM Pro",
        CONF_UPNP_LOCATION: "http://192.168.1.100:49152/description.xml",
        "model": "WiiM Pro",
    }

    flow = WiimConfigFlow()
    flow.hass = mock_hass

    with (
        patch.object(
            flow, "async_set_unique_id", new_callable=AsyncMock
        ) as mock_set_unique_id,
        patch.object(
            flow, "_abort_if_unique_id_configured", new_callable=MagicMock
        ) as mock_abort,
    ):
        mock_abort.return_value = None

        with patch(
            "homeassistant.components.wiim.config_flow._validate_device_and_get_info",
            return_value=mock_device_info,
        ):
            result = await flow.async_step_user({CONF_HOST: "192.168.1.100"})

        assert result["type"] == "create_entry"
        assert result["title"] == "WiiM Pro"
        assert result["data"][CONF_HOST] == "192.168.1.100"
        assert result["data"][CONF_UDN] == "uuid:test-1234"
        assert (
            result["data"][CONF_UPNP_LOCATION]
            == "http://192.168.1.100:49152/description.xml"
        )

        mock_set_unique_id.assert_called_once_with("uuid:test-1234")
        mock_abort.assert_called_once()


@pytest.mark.asyncio
async def test_async_step_user_already_configured(
    hass: HomeAssistant, flow, mock_config_entry
) -> None:
    """Test the user step when device is already configured."""

    domain = "wiim"
    test_udn = "uuid:test-1234"
    mock_device_info = {
        CONF_HOST: "192.168.1.100",
        CONF_UDN: test_udn,
        CONF_NAME: "WiiM Pro",
        CONF_UPNP_LOCATION: "http://192.168.1.100:49152/description.xml",
    }
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=test_udn)

    user_input = {CONF_HOST: "192.168.1.100"}

    result = await hass.config_entries.flow.async_init(
        domain, context={"source": "user"}
    )
    assert result["type"] == "form"
    flow_id = result["flow_id"]

    with patch(
        "homeassistant.components.wiim.config_flow._validate_device_and_get_info",
        return_value=mock_device_info,
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


class MockZeroconfServiceInfo:
    """Simple mock for zeroconf.ZeroconfServiceInfo."""

    def __init__(self) -> None:
        """Initialize the mock Zeroconf service info."""
        self.type = "_linkplay._tcp.local."
        self.name = "WiiM Pro"
        self.host = "192.168.1.100"
        self.port = 49152
        self.properties = {"uuid": "uuid:test-5678"}


@pytest.mark.asyncio
async def test_async_step_zeroconf_success(mock_hass: HomeAssistant) -> None:
    """Test zeroconf step with successful discovery."""

    flow = WiimConfigFlow()
    flow.hass = mock_hass

    mock_device_info = {
        "host": "192.168.1.123",
        "udn": "uuid:sample-udn",
        "name": "Mock WiiM",
        "upnp_location": "http://192.168.1.123:49152/description.xml",
    }

    with (
        patch.dict(flow.__dict__, {"context": {}}, clear=False),
        patch.object(flow, "async_set_unique_id", new_callable=AsyncMock),
        patch.object(flow, "_abort_if_unique_id_configured", new_callable=AsyncMock),
        patch(
            "homeassistant.components.wiim.config_flow._validate_device_and_get_info",
            return_value=mock_device_info,
        ),
    ):
        await flow.async_step_zeroconf(MockZeroconfServiceInfo())

        assert "title_placeholders" in flow.context
        assert flow.context["title_placeholders"]["name"] == mock_device_info[CONF_NAME]


@pytest.mark.asyncio
async def test_async_step_zeroconf_cannot_connect(flow, mock_upnp_factory) -> None:
    """Test zeroconf discovery when connection fails."""
    _flow, _ = flow
    mock_upnp_factory.async_create_device.side_effect = UpnpConnectionError

    _flow.async_set_unique_id = AsyncMock()
    _flow._abort_if_unique_id_configured = AsyncMock()

    with patch(
        "homeassistant.components.wiim.config_flow._validate_device_and_get_info",
        side_effect=CannotConnect("cannot_connect"),
    ):
        result = await _flow.async_step_zeroconf(MockZeroconfServiceInfo())

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


@pytest.mark.asyncio
async def test_async_step_discovery_confirm_create_entry(
    flow, mock_upnp_factory, mock_wiim_api_endpoint
) -> None:
    """Test discovery confirm step creates entry with user input."""
    _flow, _ = flow

    _flow._discovered_info = {
        CONF_HOST: "192.168.1.100",
        CONF_UDN: "uuid:test-udn-1234",
        CONF_NAME: "Discovered WiiM Device",
        CONF_UPNP_LOCATION: "http://192.168.1.100:49152/description.xml",
    }

    user_input = {}
    result = await _flow.async_step_discovery_confirm(user_input)

    assert result["type"] == "create_entry"
    assert result["title"] == "Discovered WiiM Device"
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_UDN] == "uuid:test-udn-1234"
    assert (
        result["data"][CONF_UPNP_LOCATION]
        == "http://192.168.1.100:49152/description.xml"
    )


@pytest.mark.asyncio
async def test_async_step_discovery_confirm_show_form(flow) -> None:
    """Test discovery confirm step shows form when no user input."""
    _flow, _ = flow

    result = await _flow.async_step_discovery_confirm()

    assert result["type"] == "form"
    assert result["step_id"] == "discovery_confirm"
    assert "Discovered WiiM Device" in result["description_placeholders"]["name"]


@pytest.mark.asyncio
async def test_validate_device_and_get_info_success(
    mock_hass: HomeAssistant, mock_upnp_device, mock_wiim_api_endpoint
) -> None:
    """Test _validate_device_and_get_info with successful validation."""
    mock_upnp_device.udn = "uuid:test-udn-1234"
    mock_upnp_device.friendly_name = "Test WiiM Device"
    mock_upnp_device.model_name = "WiiM Pro"
    mock_upnp_device.device_url = "http://192.168.1.100:49152/description.xml"

    location = "http://192.168.1.100:49152/description.xml"

    expected_result = {
        CONF_HOST: "192.168.1.100",
        CONF_UDN: "uuid:test-udn-1234",
        CONF_NAME: "Test WiiM Device",
        CONF_UPNP_LOCATION: location,
        "model": "WiiM Pro",
    }

    with patch(
        "async_upnp_client.client_factory.UpnpFactory.async_create_device",
        return_value=mock_upnp_device,
    ):
        result = await _validate_device_and_get_info(
            mock_hass, "192.168.1.100", location
        )
        assert result == expected_result
