"""The tests for the discovery component."""
from unittest.mock import MagicMock

import pytest

from homeassistant import config_entries
from homeassistant.bootstrap import async_setup_component
from homeassistant.components import discovery
from homeassistant.util.dt import utcnow

from tests.async_mock import patch
from tests.common import async_fire_time_changed, mock_coro

# One might consider to "mock" services, but it's easy enough to just use
# what is already available.
SERVICE = "yamaha"
SERVICE_COMPONENT = "media_player"

SERVICE_NO_PLATFORM = "hass_ios"
SERVICE_NO_PLATFORM_COMPONENT = "ios"
SERVICE_INFO = {"key": "value"}  # Can be anything

UNKNOWN_SERVICE = "this_service_will_never_be_supported"

BASE_CONFIG = {discovery.DOMAIN: {"ignore": [], "enable": []}}

IGNORE_CONFIG = {discovery.DOMAIN: {"ignore": [SERVICE_NO_PLATFORM]}}


@pytest.fixture(autouse=True)
def netdisco_mock():
    """Mock netdisco."""
    with patch.dict("sys.modules", {"netdisco.discovery": MagicMock()}):
        yield


async def mock_discovery(hass, discoveries, config=BASE_CONFIG):
    """Mock discoveries."""
    result = await async_setup_component(hass, "discovery", config)
    assert result

    await hass.async_start()

    with patch.object(discovery, "_discover", discoveries), patch(
        "homeassistant.components.discovery.async_discover", return_value=mock_coro()
    ) as mock_discover, patch(
        "homeassistant.components.discovery.async_load_platform",
        return_value=mock_coro(),
    ) as mock_platform:
        async_fire_time_changed(hass, utcnow())
        # Work around an issue where our loop.call_soon not get caught
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    return mock_discover, mock_platform


async def test_unknown_service(hass):
    """Test that unknown service is ignored."""

    def discover(netdisco, zeroconf_instance):
        """Fake discovery."""
        return [("this_service_will_never_be_supported", {"info": "some"})]

    mock_discover, mock_platform = await mock_discovery(hass, discover)

    assert not mock_discover.called
    assert not mock_platform.called


async def test_load_platform(hass):
    """Test load a platform."""

    def discover(netdisco, zeroconf_instance):
        """Fake discovery."""
        return [(SERVICE, SERVICE_INFO)]

    mock_discover, mock_platform = await mock_discovery(hass, discover)

    assert not mock_discover.called
    assert mock_platform.called
    mock_platform.assert_called_with(
        hass, SERVICE_COMPONENT, SERVICE, SERVICE_INFO, BASE_CONFIG
    )


async def test_load_component(hass):
    """Test load a component."""

    def discover(netdisco, zeroconf_instance):
        """Fake discovery."""
        return [(SERVICE_NO_PLATFORM, SERVICE_INFO)]

    mock_discover, mock_platform = await mock_discovery(hass, discover)

    assert mock_discover.called
    assert not mock_platform.called
    mock_discover.assert_called_with(
        hass,
        SERVICE_NO_PLATFORM,
        SERVICE_INFO,
        SERVICE_NO_PLATFORM_COMPONENT,
        BASE_CONFIG,
    )


async def test_ignore_service(hass):
    """Test ignore service."""

    def discover(netdisco, zeroconf_instance):
        """Fake discovery."""
        return [(SERVICE_NO_PLATFORM, SERVICE_INFO)]

    mock_discover, mock_platform = await mock_discovery(hass, discover, IGNORE_CONFIG)

    assert not mock_discover.called
    assert not mock_platform.called


async def test_discover_duplicates(hass):
    """Test load a component."""

    def discover(netdisco, zeroconf_instance):
        """Fake discovery."""
        return [
            (SERVICE_NO_PLATFORM, SERVICE_INFO),
            (SERVICE_NO_PLATFORM, SERVICE_INFO),
        ]

    mock_discover, mock_platform = await mock_discovery(hass, discover)

    assert mock_discover.called
    assert mock_discover.call_count == 1
    assert not mock_platform.called
    mock_discover.assert_called_with(
        hass,
        SERVICE_NO_PLATFORM,
        SERVICE_INFO,
        SERVICE_NO_PLATFORM_COMPONENT,
        BASE_CONFIG,
    )


async def test_discover_config_flow(hass):
    """Test discovery triggering a config flow."""
    discovery_info = {"hello": "world"}

    def discover(netdisco, zeroconf_instance):
        """Fake discovery."""
        return [("mock-service", discovery_info)]

    with patch.dict(
        discovery.CONFIG_ENTRY_HANDLERS, {"mock-service": "mock-component"}
    ), patch("homeassistant.data_entry_flow.FlowManager.async_init") as m_init:
        await mock_discovery(hass, discover)

    assert len(m_init.mock_calls) == 1
    args, kwargs = m_init.mock_calls[0][1:]
    assert args == ("mock-component",)
    assert kwargs["context"]["source"] == config_entries.SOURCE_DISCOVERY
    assert kwargs["data"] == discovery_info
