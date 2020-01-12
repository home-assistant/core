"""Test Zeroconf component setup process."""
from unittest.mock import patch

import pytest
from zeroconf import ServiceInfo, ServiceStateChange

from homeassistant.components import zeroconf
from homeassistant.generated import zeroconf as zc_gen
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_zeroconf():
    """Mock zeroconf."""
    with patch("homeassistant.components.zeroconf.Zeroconf") as mock_zc:
        yield mock_zc.return_value


def service_update_mock(zeroconf, service, handlers):
    """Call service update handler."""
    handlers[0](zeroconf, service, f"name.{service}", ServiceStateChange.Added)


def get_service_info_mock(service_type, name):
    """Return service info for get_service_info."""
    return ServiceInfo(
        service_type,
        name,
        address=b"\n\x00\x00\x14",
        port=80,
        weight=0,
        priority=0,
        server="name.local.",
        properties={b"macaddress": b"ABCDEF012345"},
    )


def get_homekit_info_mock(model):
    """Return homekit info for get_service_info."""

    def mock_homekit_info(service_type, name):
        return ServiceInfo(
            service_type,
            name,
            address=b"\n\x00\x00\x14",
            port=80,
            weight=0,
            priority=0,
            server="name.local.",
            properties={b"md": model.encode()},
        )

    return mock_homekit_info


async def test_setup(hass, mock_zeroconf):
    """Test configured options for a device are loaded via config entry."""
    with patch.object(hass.config_entries, "flow") as mock_config_flow, patch.object(
        zeroconf, "ServiceBrowser", side_effect=service_update_mock
    ) as mock_service_browser:
        mock_zeroconf.get_service_info.side_effect = get_service_info_mock
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})

    assert len(mock_service_browser.mock_calls) == len(zc_gen.ZEROCONF)
    assert len(mock_config_flow.mock_calls) == len(zc_gen.ZEROCONF) * 2


async def test_homekit_match_partial(hass, mock_zeroconf):
    """Test configured options for a device are loaded via config entry."""
    with patch.dict(
        zc_gen.ZEROCONF, {zeroconf.HOMEKIT_TYPE: ["homekit_controller"]}, clear=True
    ), patch.object(hass.config_entries, "flow") as mock_config_flow, patch.object(
        zeroconf, "ServiceBrowser", side_effect=service_update_mock
    ) as mock_service_browser:
        mock_zeroconf.get_service_info.side_effect = get_homekit_info_mock("LIFX bulb")
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 2
    assert mock_config_flow.mock_calls[0][1][0] == "lifx"


async def test_homekit_match_full(hass, mock_zeroconf):
    """Test configured options for a device are loaded via config entry."""
    with patch.dict(
        zc_gen.ZEROCONF, {zeroconf.HOMEKIT_TYPE: ["homekit_controller"]}, clear=True
    ), patch.object(hass.config_entries, "flow") as mock_config_flow, patch.object(
        zeroconf, "ServiceBrowser", side_effect=service_update_mock
    ) as mock_service_browser:
        mock_zeroconf.get_service_info.side_effect = get_homekit_info_mock("BSB002")
        assert await async_setup_component(hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})

    assert len(mock_service_browser.mock_calls) == 1
    assert len(mock_config_flow.mock_calls) == 2
    assert mock_config_flow.mock_calls[0][1][0] == "hue"
