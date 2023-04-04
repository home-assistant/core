"""The tests for the discovery component."""
from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.bootstrap import async_setup_component
from homeassistant.components import discovery
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed, mock_coro

# One might consider to "mock" services, but it's easy enough to just use
# what is already available.
SERVICE = "yamaha"
SERVICE_COMPONENT = "media_player"

SERVICE_INFO = {"key": "value"}  # Can be anything

UNKNOWN_SERVICE = "this_service_will_never_be_supported"

BASE_CONFIG = {discovery.DOMAIN: {"ignore": [], "enable": []}}


@pytest.fixture(autouse=True)
def netdisco_mock():
    """Mock netdisco."""
    with patch.dict("sys.modules", {"netdisco.discovery": MagicMock()}):
        yield


async def mock_discovery(hass, discoveries, config=BASE_CONFIG):
    """Mock discoveries."""
    with patch("homeassistant.components.zeroconf.async_get_instance"), patch(
        "homeassistant.components.zeroconf.async_setup", return_value=True
    ), patch.object(discovery, "_discover", discoveries), patch(
        "homeassistant.components.discovery.async_discover"
    ) as mock_discover, patch(
        "homeassistant.components.discovery.async_load_platform",
        return_value=mock_coro(),
    ) as mock_platform:
        assert await async_setup_component(hass, "discovery", config)
        await hass.async_block_till_done()
        await hass.async_start()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, utcnow())
        # Work around an issue where our loop.call_soon not get caught
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    return mock_discover, mock_platform


async def test_unknown_service(hass: HomeAssistant) -> None:
    """Test that unknown service is ignored."""

    def discover(netdisco, zeroconf_instance, suppress_mdns_types):
        """Fake discovery."""
        return [("this_service_will_never_be_supported", {"info": "some"})]

    mock_discover, mock_platform = await mock_discovery(hass, discover)

    assert not mock_discover.called
    assert not mock_platform.called


async def test_load_platform(hass: HomeAssistant) -> None:
    """Test load a platform."""

    def discover(netdisco, zeroconf_instance, suppress_mdns_types):
        """Fake discovery."""
        return [(SERVICE, SERVICE_INFO)]

    mock_discover, mock_platform = await mock_discovery(hass, discover)

    assert not mock_discover.called
    assert mock_platform.called
    mock_platform.assert_called_with(
        hass, SERVICE_COMPONENT, SERVICE, SERVICE_INFO, BASE_CONFIG
    )


async def test_discover_config_flow(hass: HomeAssistant) -> None:
    """Test discovery triggering a config flow."""
    discovery_info = {"hello": "world"}

    def discover(netdisco, zeroconf_instance, suppress_mdns_types):
        """Fake discovery."""
        return [("mock-service", discovery_info)]

    with patch.dict(
        discovery.CONFIG_ENTRY_HANDLERS, {"mock-service": "mock-component"}
    ), patch(
        "homeassistant.config_entries.ConfigEntriesFlowManager.async_init"
    ) as m_init:
        await mock_discovery(hass, discover)

    assert len(m_init.mock_calls) == 1
    args, kwargs = m_init.mock_calls[0][1:]
    assert args == ("mock-component",)
    assert kwargs["context"]["source"] == config_entries.SOURCE_DISCOVERY
    assert kwargs["data"] == discovery_info
