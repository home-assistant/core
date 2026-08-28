"""Test the UniFi Discovery init."""

from typing import Any

import pytest
from unifi_discovery import UnifiDevice

from homeassistant import config_entries
from homeassistant.components.unifi_discovery.const import DOMAIN
from homeassistant.components.unifi_discovery.discovery import (
    _announced_ips,
    _device_to_dict,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    UNIFI_DISCOVERY_MAPPINGPROXY_SERVICES,
    UNIFI_DISCOVERY_NO_MAC,
    _patch_discovery,
)


async def test_setup_starts_discovery(hass: HomeAssistant) -> None:
    """Test that async_setup starts discovery and dispatches flows."""
    with _patch_discovery():
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done(wait_background_tasks=True)

    # The scanner should have dispatched a discovery flow for the Protect consumer
    flows = hass.config_entries.flow.async_progress_by_handler("unifiprotect")
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY


async def test_setup_no_devices(hass: HomeAssistant) -> None:
    """Test setup with no devices found."""
    with _patch_discovery(no_device=True):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler("unifiprotect")
    assert len(flows) == 0


async def test_setup_device_without_mac(hass: HomeAssistant) -> None:
    """Test that devices without hw_addr are skipped."""
    with _patch_discovery(device=UNIFI_DISCOVERY_NO_MAC):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler("unifiprotect")
    assert len(flows) == 0


async def test_dependency_loads_discovery(
    hass: HomeAssistant,
) -> None:
    """Test that loading unifiprotect triggers unifi_discovery as dependency."""
    with _patch_discovery():
        assert await async_setup_component(hass, "unifiprotect", {})
        await hass.async_block_till_done(wait_background_tasks=True)

    # unifi_discovery should have been loaded as a dependency and started scanning
    flows = hass.config_entries.flow.async_progress_by_handler("unifiprotect")
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY


async def test_discovery_does_not_deepcopy_device(hass: HomeAssistant) -> None:
    """Test discovery works without deepcopy.

    In production asdict() deep-copies Enum keys in the services dict which
    can crash on Python 3.14+ because Enum.__members__ is a mappingproxy that
    cannot be pickled.  We force the crash reliably by using MappingProxyType
    as the services value.
    """
    with _patch_discovery(device=UNIFI_DISCOVERY_MAPPINGPROXY_SERVICES):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler("unifiprotect")
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == config_entries.SOURCE_INTEGRATION_DISCOVERY


@pytest.mark.parametrize(
    ("device_kwargs", "expected"),
    [
        pytest.param({}, [], id="nothing_announced"),
        pytest.param(
            {
                "ip_info": (
                    "aa:bb:cc:dd:ee:fd;192.168.1.1",
                    "aa:bb:cc:dd:ee:fd;192.168.2.1",
                    "aa:bb:cc:dd:ee:fb;10.0.0.5",
                )
            },
            ["192.168.1.1", "192.168.2.1", "10.0.0.5"],
            id="every_interface",
        ),
        pytest.param(
            {
                "ip_info": (
                    "aa:bb:cc:dd:ee:fd;192.168.1.1",
                    # Upstream WAN and neighbours the console also reports.
                    "00:00:00:00:00:00;198.51.100.7",
                    "00:00:00:00:00:00;192.168.0.0",
                    "5a:71:71:7a:68:8e;192.168.1.9",
                    # Another Ubiquiti device: same OUI, different unit.
                    "aa:bb:cc:99:99:01;192.168.1.10",
                )
            },
            ["192.168.1.1"],
            id="foreign_addresses_dropped",
        ),
        pytest.param(
            {"ip_info": ("aa:bb:cc:dd:ee:fd;", "aa:bb:cc:dd:ee:fd")},
            [],
            id="malformed_entries",
        ),
        pytest.param(
            {"primary_addr": "aa:bb:cc:dd:ee:ff;192.168.1.1"},
            ["192.168.1.1"],
            id="primary_addr",
        ),
        pytest.param(
            {
                "ip_info": ("aa:bb:cc:dd:ee:fd;192.168.1.1",),
                "primary_addr": "aa:bb:cc:dd:ee:ff;192.168.1.1",
            },
            ["192.168.1.1"],
            id="deduplicated",
        ),
    ],
)
def test_announced_ips(device_kwargs: dict[str, Any], expected: list[str]) -> None:
    """Test only the device's own announced addresses are returned."""
    device = UnifiDevice(
        source_ip="192.168.1.1", hw_addr="aa:bb:cc:dd:ee:ff", **device_kwargs
    )
    assert _announced_ips(device) == expected


def test_announced_ips_without_mac() -> None:
    """Test a device without hw_addr announces nothing identifiable."""
    device = UnifiDevice(
        source_ip="192.168.1.1", ip_info=("aa:bb:cc:dd:ee:fd;192.168.1.1",)
    )
    assert _announced_ips(device) == []


def test_device_to_dict_carries_announced_ips() -> None:
    """Test the announced addresses reach the payload the consumers receive."""
    device = UnifiDevice(
        source_ip="192.168.1.1",
        hw_addr="aa:bb:cc:dd:ee:ff",
        ip_info=("aa:bb:cc:dd:ee:fd;192.168.2.1",),
    )
    assert _device_to_dict(device)["announced_ips"] == ["192.168.2.1"]
