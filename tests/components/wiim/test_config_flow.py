"""pytest config_flow.py."""

from unittest.mock import AsyncMock, MagicMock, patch

from async_upnp_client.exceptions import UpnpConnectionError
import pytest
from wiim.exceptions import WiimRequestException

from homeassistant.components.wiim.config_flow import (
    CannotConnect,
    NotWiimDevice,
    WiimConfigFlow,
    _validate_device_and_get_info,
)
from homeassistant.components.wiim.const import CONF_UDN, CONF_UPNP_LOCATION
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow


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
            flow, "_abort_if_unique_id_configured", new_callable=AsyncMock
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
async def test_async_step_user_already_configured(flow, mock_config_entry) -> None:
    """Test the user step when device is already configured."""
    _flow, hass = flow
    mock_config_entry.data[CONF_UDN] = "uuid:test-udn-1234"  # Ensure UDN matches
    hass.config_entries.async_entries.return_value = [mock_config_entry]

    mock_device_info = {
        CONF_HOST: "192.168.1.100",
        CONF_UDN: "uuid:test-1234",
        CONF_NAME: "WiiM Pro",
        CONF_UPNP_LOCATION: "http://192.168.1.100:49152/description.xml",
        "model": "WiiM Pro",
    }

    _flow.async_set_unique_id = AsyncMock()

    user_input = {CONF_HOST: "192.168.1.100"}
    with patch(
        "homeassistant.components.wiim.config_flow._validate_device_and_get_info",
        return_value=mock_device_info,
    ):
        result = await _flow.async_step_user(user_input)

    assert result["type"] == "create_entry"


@pytest.mark.asyncio
async def test_async_step_import_success(mocker, flow, mock_hass) -> None:
    """Test async_step_import creates entry when config is valid."""
    flow = WiimConfigFlow()
    flow.hass = mock_hass

    import_config = {
        CONF_HOST: "192.168.1.50",
        CONF_UDN: "uuid:test-udn",
        CONF_NAME: "My WiiM",
        CONF_UPNP_LOCATION: "http://192.168.1.50:49152/description.xml",
    }

    # Mock methods
    mocker.patch.object(flow, "async_set_unique_id", new=AsyncMock())
    mocker.patch.object(flow, "_abort_if_unique_id_configured", new=AsyncMock())
    mocker.patch.object(
        flow, "async_create_entry", new=AsyncMock(return_value={"type": "create_entry"})
    )

    await flow.async_step_import(import_config)

    flow.async_set_unique_id.assert_awaited_once_with("uuid:test-udn")
    flow._abort_if_unique_id_configured.assert_called_once()
    flow.async_create_entry.assert_called_once_with(
        title="My WiiM",
        data={
            "host": "192.168.1.50",
            "udn": "uuid:test-udn",
            "name": "My WiiM",
            "upnp_location": "http://192.168.1.50:49152/description.xml",
        },
    )


@pytest.mark.asyncio
async def test_async_step_import_missing_udn(mocker, flow, mock_hass) -> None:
    """Test async_step_import aborts if UDN missing in config."""
    flow = WiimConfigFlow()
    flow.hass = mock_hass

    import_config = {
        CONF_HOST: "192.168.1.50",
        CONF_NAME: "My WiiM",
        CONF_UPNP_LOCATION: "http://192.168.1.50:49152/description.xml",
    }

    flow.async_abort = MagicMock(
        return_value={"type": "abort", "reason": "invalid_import_data"}
    )

    result = await flow.async_step_import(import_config)

    flow.async_abort.assert_called_once_with(reason="invalid_import_data")
    assert result["type"] == "abort"


@pytest.mark.asyncio
async def test_async_step_import_already_configured(mocker, flow, mock_hass) -> None:
    """Test async_step_import aborts if unique ID already configured."""
    flow = WiimConfigFlow()
    flow.hass = mock_hass

    import_config = {
        CONF_HOST: "192.168.1.50",
        CONF_UDN: "uuid:existing-udn",
        CONF_NAME: "Existing WiiM",
        CONF_UPNP_LOCATION: "http://192.168.1.50:49152/description.xml",
    }

    mocker.patch.object(WiimConfigFlow, "async_set_unique_id", new=AsyncMock())
    mocker.patch.object(
        WiimConfigFlow,
        "_abort_if_unique_id_configured",
        side_effect=AbortFlow("already_configured"),
    )
    with pytest.raises(AbortFlow) as exc_info:
        await flow.async_step_import(import_config)

    flow.async_set_unique_id.assert_awaited_once_with("uuid:existing-udn")
    flow._abort_if_unique_id_configured.assert_called_once()

    assert "already_configured" in str(exc_info.value)


@pytest.mark.asyncio
async def test_async_step_user_not_wiim_device(
    flow, mock_upnp_factory, mock_wiim_api_endpoint
) -> None:
    """Test the user step when discovered device is not a WiiM device."""
    _flow, _ = flow
    mock_wiim_api_endpoint.json_request.side_effect = WiimRequestException(
        "Not a WiiM device"
    )

    with patch(
        "homeassistant.components.wiim.config_flow._validate_device_and_get_info",
        side_effect=NotWiimDevice("Not a WiiM device"),
    ):
        result = await _flow.async_step_user({CONF_HOST: "192.168.1.100"})

    assert result["type"] == "form"
    assert result["errors"]["base"] == "not_wiim_device"


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
