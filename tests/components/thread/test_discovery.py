"""Test the thread websocket API."""

from unittest.mock import ANY, AsyncMock, MagicMock, Mock

import pytest
from zeroconf.asyncio import AsyncServiceInfo

from homeassistant.components.thread import discovery
from homeassistant.components.thread.const import DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component

from . import (
    ROUTER_DISCOVERY_GOOGLE_1,
    ROUTER_DISCOVERY_HASS,
    ROUTER_DISCOVERY_HASS_BAD_DATA,
    ROUTER_DISCOVERY_HASS_BAD_STATE_BITMAP,
    ROUTER_DISCOVERY_HASS_MISSING_DATA,
    ROUTER_DISCOVERY_HASS_MISSING_MANDATORY_DATA_XA,
    ROUTER_DISCOVERY_HASS_MISSING_MANDATORY_DATA_XP,
    ROUTER_DISCOVERY_HASS_NO_ACTIVE_TIMESTAMP,
    ROUTER_DISCOVERY_HASS_NO_STATE_BITMAP,
    ROUTER_DISCOVERY_HASS_STATE_BITMAP_NOT_ACTIVE,
)


async def test_discover_routers(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock
) -> None:
    """Test discovering thread routers."""
    mock_async_zeroconf.async_add_service_listener = AsyncMock()
    mock_async_zeroconf.async_remove_service_listener = AsyncMock()
    mock_async_zeroconf.async_get_service_info = AsyncMock()

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    discovered = []
    removed = []

    @callback
    def router_discovered(key: str, data: discovery.ThreadRouterDiscoveryData) -> None:
        """Handle router discovered."""
        discovered.append((key, data))

    @callback
    def router_removed(key: str) -> None:
        """Handle router removed."""
        removed.append(key)

    # Start Thread router discovery
    thread_disovery = discovery.ThreadRouterDiscovery(
        hass, router_discovered, router_removed
    )
    await thread_disovery.async_start()

    mock_async_zeroconf.async_add_service_listener.assert_called_once_with(
        "_meshcop._udp.local.", ANY
    )
    listener: discovery.ThreadRouterDiscovery.ThreadServiceListener = (
        mock_async_zeroconf.async_add_service_listener.mock_calls[0][1][1]
    )

    # Discover a service
    mock_async_zeroconf.async_get_service_info.return_value = AsyncServiceInfo(
        **ROUTER_DISCOVERY_HASS
    )
    listener.add_service(
        None, ROUTER_DISCOVERY_HASS["type_"], ROUTER_DISCOVERY_HASS["name"]
    )
    await hass.async_block_till_done()
    assert len(discovered) == 1
    assert len(removed) == 0
    assert discovered[-1] == (
        "aeeb2f594b570bbf",
        discovery.ThreadRouterDiscoveryData(
            addresses=["192.168.0.115"],
            border_agent_id="230c6a1ac57f6f4be262acf32e5ef52c",
            brand="homeassistant",
            extended_address="aeeb2f594b570bbf",
            extended_pan_id="e60fc7c186212ce5",
            model_name="OpenThreadBorderRouter",
            network_name="OpenThread HC",
            server="core-silabs-multiprotocol.local.",
            thread_version="1.3.0",
            unconfigured=None,
            vendor_name="HomeAssistant",
        ),
    )

    # Discover another service - we don't care if zeroconf considers this an update
    mock_async_zeroconf.async_get_service_info.return_value = AsyncServiceInfo(
        **ROUTER_DISCOVERY_GOOGLE_1
    )
    listener.update_service(
        None, ROUTER_DISCOVERY_GOOGLE_1["type_"], ROUTER_DISCOVERY_GOOGLE_1["name"]
    )
    await hass.async_block_till_done()
    assert len(discovered) == 2
    assert len(removed) == 0
    assert discovered[-1] == (
        "f6a99b425a67abed",
        discovery.ThreadRouterDiscoveryData(
            addresses=["192.168.0.124"],
            border_agent_id="bc3740c3e963aa8735bebecd7cc503c7",
            brand="google",
            extended_address="f6a99b425a67abed",
            extended_pan_id="9e75e256f61409a3",
            model_name="Google Nest Hub",
            network_name="NEST-PAN-E1AF",
            server="2d99f293-cd8e-2770-8dd2-6675de9fa000.local.",
            thread_version="1.3.0",
            unconfigured=None,
            vendor_name="Google Inc.",
        ),
    )

    # Remove a service
    listener.remove_service(
        None, ROUTER_DISCOVERY_HASS["type_"], ROUTER_DISCOVERY_HASS["name"]
    )
    await hass.async_block_till_done()
    assert len(discovered) == 2
    assert len(removed) == 1
    assert removed[-1] == "aeeb2f594b570bbf"

    # Remove the service again
    listener.remove_service(
        None, ROUTER_DISCOVERY_HASS["type_"], ROUTER_DISCOVERY_HASS["name"]
    )
    await hass.async_block_till_done()
    assert len(discovered) == 2
    assert len(removed) == 1

    # Remove an unknown service
    listener.remove_service(None, ROUTER_DISCOVERY_HASS["type_"], "unknown")
    await hass.async_block_till_done()
    assert len(discovered) == 2
    assert len(removed) == 1

    # Stop Thread router discovery
    await thread_disovery.async_stop()
    mock_async_zeroconf.async_remove_service_listener.assert_called_once_with(listener)


@pytest.mark.parametrize(
    ("data", "unconfigured"),
    [
        (ROUTER_DISCOVERY_HASS_NO_ACTIVE_TIMESTAMP, True),
        (ROUTER_DISCOVERY_HASS_BAD_STATE_BITMAP, None),
        (ROUTER_DISCOVERY_HASS_NO_STATE_BITMAP, None),
        (ROUTER_DISCOVERY_HASS_STATE_BITMAP_NOT_ACTIVE, True),
    ],
)
async def test_discover_routers_unconfigured(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock, data, unconfigured
) -> None:
    """Test discovering thread routers and setting the unconfigured flag."""
    mock_async_zeroconf.async_add_service_listener = AsyncMock()
    mock_async_zeroconf.async_remove_service_listener = AsyncMock()
    mock_async_zeroconf.async_get_service_info = AsyncMock()

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Start Thread router discovery
    router_discovered_removed = Mock()
    thread_disovery = discovery.ThreadRouterDiscovery(
        hass, router_discovered_removed, router_discovered_removed
    )
    await thread_disovery.async_start()
    listener: discovery.ThreadRouterDiscovery.ThreadServiceListener = (
        mock_async_zeroconf.async_add_service_listener.mock_calls[0][1][1]
    )

    # Discover a service with bad or missing data
    mock_async_zeroconf.async_get_service_info.return_value = AsyncServiceInfo(**data)
    listener.add_service(None, data["type_"], data["name"])
    await hass.async_block_till_done()
    router_discovered_removed.assert_called_once_with(
        "aeeb2f594b570bbf",
        discovery.ThreadRouterDiscoveryData(
            addresses=["192.168.0.115"],
            border_agent_id="230c6a1ac57f6f4be262acf32e5ef52c",
            brand="homeassistant",
            extended_address="aeeb2f594b570bbf",
            extended_pan_id="e60fc7c186212ce5",
            model_name="OpenThreadBorderRouter",
            network_name="OpenThread HC",
            server="core-silabs-multiprotocol.local.",
            thread_version="1.3.0",
            unconfigured=unconfigured,
            vendor_name="HomeAssistant",
        ),
    )


@pytest.mark.parametrize(
    "data", [ROUTER_DISCOVERY_HASS_BAD_DATA, ROUTER_DISCOVERY_HASS_MISSING_DATA]
)
async def test_discover_routers_bad_or_missing_optional_data(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock, data
) -> None:
    """Test discovering thread routers with bad or missing vendor mDNS data."""
    mock_async_zeroconf.async_add_service_listener = AsyncMock()
    mock_async_zeroconf.async_remove_service_listener = AsyncMock()
    mock_async_zeroconf.async_get_service_info = AsyncMock()

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Start Thread router discovery
    router_discovered_removed = Mock()
    thread_disovery = discovery.ThreadRouterDiscovery(
        hass, router_discovered_removed, router_discovered_removed
    )
    await thread_disovery.async_start()
    listener: discovery.ThreadRouterDiscovery.ThreadServiceListener = (
        mock_async_zeroconf.async_add_service_listener.mock_calls[0][1][1]
    )

    # Discover a service with bad or missing data
    mock_async_zeroconf.async_get_service_info.return_value = AsyncServiceInfo(**data)
    listener.add_service(None, data["type_"], data["name"])
    await hass.async_block_till_done()
    router_discovered_removed.assert_called_once_with(
        "aeeb2f594b570bbf",
        discovery.ThreadRouterDiscoveryData(
            addresses=["192.168.0.115"],
            border_agent_id="230c6a1ac57f6f4be262acf32e5ef52c",
            brand=None,
            extended_address="aeeb2f594b570bbf",
            extended_pan_id="e60fc7c186212ce5",
            model_name="OpenThreadBorderRouter",
            network_name="OpenThread HC",
            server="core-silabs-multiprotocol.local.",
            thread_version="1.3.0",
            unconfigured=None,
            vendor_name=None,
        ),
    )


@pytest.mark.parametrize(
    "service",
    [
        ROUTER_DISCOVERY_HASS_MISSING_MANDATORY_DATA_XA,
        ROUTER_DISCOVERY_HASS_MISSING_MANDATORY_DATA_XP,
    ],
)
async def test_discover_routers_bad_or_missing_mandatory_data(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock, service
) -> None:
    """Test discovering thread routers with missing mandatory mDNS data."""
    mock_async_zeroconf.async_add_service_listener = AsyncMock()
    mock_async_zeroconf.async_remove_service_listener = AsyncMock()
    mock_async_zeroconf.async_get_service_info = AsyncMock()

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Start Thread router discovery
    router_discovered_removed = Mock()
    thread_disovery = discovery.ThreadRouterDiscovery(
        hass, router_discovered_removed, router_discovered_removed
    )
    await thread_disovery.async_start()
    listener: discovery.ThreadRouterDiscovery.ThreadServiceListener = (
        mock_async_zeroconf.async_add_service_listener.mock_calls[0][1][1]
    )

    # Discover a service with missing mandatory data
    mock_async_zeroconf.async_get_service_info.return_value = AsyncServiceInfo(
        **service
    )
    listener.add_service(
        None,
        service["type_"],
        service["name"],
    )
    await hass.async_block_till_done()
    router_discovered_removed.assert_not_called()


async def test_discover_routers_get_service_info_fails(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock
) -> None:
    """Test discovering thread routers with invalid mDNS data."""
    mock_async_zeroconf.async_add_service_listener = AsyncMock()
    mock_async_zeroconf.async_remove_service_listener = AsyncMock()
    mock_async_zeroconf.async_get_service_info = AsyncMock()

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Start Thread router discovery
    router_discovered_removed = Mock()
    thread_disovery = discovery.ThreadRouterDiscovery(
        hass, router_discovered_removed, router_discovered_removed
    )
    await thread_disovery.async_start()
    listener: discovery.ThreadRouterDiscovery.ThreadServiceListener = (
        mock_async_zeroconf.async_add_service_listener.mock_calls[0][1][1]
    )

    # Discover a service with missing data
    mock_async_zeroconf.async_get_service_info.return_value = None
    listener.add_service(
        None, ROUTER_DISCOVERY_HASS["type_"], ROUTER_DISCOVERY_HASS["name"]
    )
    await hass.async_block_till_done()
    router_discovered_removed.assert_not_called()


async def test_discover_routers_update_unchanged(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock
) -> None:
    """Test discovering thread routers with identical mDNS data in update."""
    mock_async_zeroconf.async_add_service_listener = AsyncMock()
    mock_async_zeroconf.async_remove_service_listener = AsyncMock()
    mock_async_zeroconf.async_get_service_info = AsyncMock()

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Start Thread router discovery
    router_discovered_removed = Mock()
    thread_disovery = discovery.ThreadRouterDiscovery(
        hass, router_discovered_removed, router_discovered_removed
    )
    await thread_disovery.async_start()
    listener: discovery.ThreadRouterDiscovery.ThreadServiceListener = (
        mock_async_zeroconf.async_add_service_listener.mock_calls[0][1][1]
    )

    # Discover a service
    mock_async_zeroconf.async_get_service_info.return_value = AsyncServiceInfo(
        **ROUTER_DISCOVERY_HASS
    )
    listener.add_service(
        None, ROUTER_DISCOVERY_HASS["type_"], ROUTER_DISCOVERY_HASS["name"]
    )
    await hass.async_block_till_done()
    router_discovered_removed.assert_called_once()

    # Update the service unchanged
    mock_async_zeroconf.async_get_service_info.return_value = AsyncServiceInfo(
        **ROUTER_DISCOVERY_HASS
    )
    listener.update_service(
        None, ROUTER_DISCOVERY_HASS["type_"], ROUTER_DISCOVERY_HASS["name"]
    )
    await hass.async_block_till_done()
    router_discovered_removed.assert_called_once()


async def test_discover_routers_stop_twice(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock
) -> None:
    """Test discovering thread routers stopping discovery twice."""
    mock_async_zeroconf.async_add_service_listener = AsyncMock()
    mock_async_zeroconf.async_remove_service_listener = AsyncMock()
    mock_async_zeroconf.async_get_service_info = AsyncMock()

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Start Thread router discovery
    router_discovered_removed = Mock()
    thread_disovery = discovery.ThreadRouterDiscovery(
        hass, router_discovered_removed, router_discovered_removed
    )
    await thread_disovery.async_start()

    # Stop Thread router discovery
    await thread_disovery.async_stop()
    mock_async_zeroconf.async_remove_service_listener.assert_called_once()

    # Stop Thread router discovery again
    await thread_disovery.async_stop()
    mock_async_zeroconf.async_remove_service_listener.assert_called_once()
