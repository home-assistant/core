"""Test hassio system health."""

import asyncio
from ipaddress import IPv4Address, IPv4Network
import os
from unittest.mock import patch

from aiohasupervisor.models import (
    AddonStage,
    AddonState,
    DockerNetwork,
    HostInfo,
    InstalledAddon,
    InterfaceMethod,
    InterfaceType,
    IPv4,
    LogLevel,
    NetworkInfo,
    NetworkInterface,
    OSInfo,
    RootInfo,
    SupervisorInfo,
    SupervisorState,
    UpdateChannel,
)
from aiohttp import ClientError
import pytest

from homeassistant.components.hassio.const import (
    DATA_ADDONS_LIST,
    DATA_HOST_INFO,
    DATA_INFO,
    DATA_NETWORK_INFO,
    DATA_OS_INFO,
    DATA_SUPERVISOR_INFO,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .test_init import MOCK_ENVIRON

from tests.common import get_system_health_info
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.usefixtures(
    "supervisor_root_info", "host_info", "os_info", "supervisor_info"
)
async def test_hassio_system_health(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test hassio system health."""
    aioclient_mock.get("http://127.0.0.1/supervisor/ping", text="")
    aioclient_mock.get("https://version.home-assistant.io/stable.json", text="")

    hass.config.components.add("hassio")
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    hass.data[DATA_INFO] = RootInfo(
        supervisor="2020.11.1",
        homeassistant=None,
        hassos="5.9",
        docker="19.0.3",
        hostname=None,
        operating_system=None,
        features=[],
        machine=None,
        machine_id=None,
        arch="aarch64",
        state=SupervisorState.RUNNING,
        supported_arch=[],
        supported=True,
        channel=UpdateChannel.STABLE,
        logging=LogLevel.INFO,
        timezone="Etc/UTC",
    )
    hass.data[DATA_HOST_INFO] = HostInfo(
        agent_version="1337",
        apparmor_version=None,
        chassis="vm",
        virtualization="qemu",
        cpe=None,
        deployment=None,
        disk_free=1.6,
        disk_total=32.0,
        disk_used=30.0,
        disk_life_time=None,
        features=[],
        hostname=None,
        llmnr_hostname=None,
        kernel="4.19.0",
        operating_system="Home Assistant OS 5.9",
        timezone=None,
        dt_utc=None,
        dt_synchronized=True,
        use_ntp=None,
        startup_time=None,
        boot_timestamp=None,
        broadcast_llmnr=None,
        broadcast_mdns=None,
    )
    hass.data[DATA_OS_INFO] = OSInfo(
        version="5.9",
        version_latest="5.9",
        update_available=False,
        board="odroid-n2",
        boot=None,
        data_disk=None,
        boot_slots={},
    )
    hass.data[DATA_SUPERVISOR_INFO] = SupervisorInfo(
        version="1.0.0",
        version_latest="1.0.0",
        update_available=False,
        channel=UpdateChannel.STABLE,
        arch="aarch64",
        supported=True,
        healthy=True,
        ip_address=IPv4Address("172.30.32.2"),
        timezone=None,
        logging=LogLevel.INFO,
        debug=False,
        debug_block=False,
        diagnostics=None,
        auto_update=True,
        country=None,
        detect_blocking_io=False,
    )
    hass.data[DATA_ADDONS_LIST] = [
        InstalledAddon(
            detached=False,
            advanced=False,
            available=True,
            build=False,
            description="",
            homeassistant=None,
            icon=False,
            logo=False,
            name="Awesome Addon",
            repository="core",
            slug="test",
            stage=AddonStage.STABLE,
            update_available=False,
            url=None,
            version_latest="1.0.0",
            version="1.0.0",
            state=AddonState.STARTED,
        )
    ]
    hass.data[DATA_NETWORK_INFO] = NetworkInfo(
        interfaces=[
            NetworkInterface(
                interface="eth0",
                type=InterfaceType.ETHERNET,
                enabled=True,
                connected=True,
                primary=False,
                mac="aa:bb:cc:dd:ee:01",
                ipv4=IPv4(
                    method=InterfaceMethod.AUTO,
                    ready=True,
                    address=[],
                    nameservers=[IPv4Address("9.9.9.9")],
                    gateway=None,
                    route_metric=None,
                ),
                ipv6=None,
                wifi=None,
                vlan=None,
                mdns=None,
                llmnr=None,
            ),
            NetworkInterface(
                interface="eth1",
                type=InterfaceType.ETHERNET,
                enabled=True,
                connected=True,
                primary=True,
                mac="aa:bb:cc:dd:ee:02",
                ipv4=IPv4(
                    method=InterfaceMethod.AUTO,
                    ready=True,
                    address=[],
                    nameservers=[IPv4Address("1.1.1.1")],
                    gateway=None,
                    route_metric=None,
                ),
                ipv6=None,
                wifi=None,
                vlan=None,
                mdns=None,
                llmnr=None,
            ),
        ],
        docker=DockerNetwork(
            interface="hassio",
            address=IPv4Network("172.30.32.0/23"),
            gateway=IPv4Address("172.30.32.1"),
            dns=IPv4Address("172.30.32.3"),
        ),
        host_internet=True,
        supervisor_internet=True,
    )

    with patch.dict(os.environ, MOCK_ENVIRON):
        info = await get_system_health_info(hass, "hassio")

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info == {
        "agent_version": "1337",
        "board": "odroid-n2",
        "disk_total": "32.0 GB",
        "disk_used": "30.0 GB",
        "docker_version": "19.0.3",
        "healthy": True,
        "host_connectivity": True,
        "supervisor_connectivity": True,
        "host_os": "Home Assistant OS 5.9",
        "installed_addons": "Awesome Addon (1.0.0)",
        "ntp_synchronized": True,
        "nameservers": "1.1.1.1",
        "supervisor_api": "ok",
        "supervisor_version": "supervisor-2020.11.1",
        "supported": True,
        "update_channel": "stable",
        "version_api": "ok",
        "virtualization": "qemu",
    }


@pytest.mark.usefixtures(
    "supervisor_root_info", "host_info", "os_info", "supervisor_info"
)
async def test_hassio_system_health_with_issues(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test hassio system health."""
    aioclient_mock.get("http://127.0.0.1/supervisor/ping", text="")
    aioclient_mock.get("https://version.home-assistant.io/stable.json", exc=ClientError)

    hass.config.components.add("hassio")
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    hass.data[DATA_INFO] = RootInfo(
        supervisor="1.0.0",
        homeassistant=None,
        hassos=None,
        docker="19.0.3",
        hostname=None,
        operating_system=None,
        features=[],
        machine=None,
        machine_id=None,
        arch="aarch64",
        state=SupervisorState.RUNNING,
        supported_arch=[],
        supported=True,
        channel=UpdateChannel.STABLE,
        logging=LogLevel.INFO,
        timezone="Etc/UTC",
    )
    hass.data[DATA_HOST_INFO] = HostInfo(
        agent_version=None,
        apparmor_version=None,
        chassis="vm",
        virtualization=None,
        cpe=None,
        deployment=None,
        disk_free=1.6,
        disk_total=100.0,
        disk_used=98.4,
        disk_life_time=None,
        features=[],
        hostname=None,
        llmnr_hostname=None,
        kernel=None,
        operating_system=None,
        timezone=None,
        dt_utc=None,
        dt_synchronized=None,
        use_ntp=None,
        startup_time=None,
        boot_timestamp=None,
        broadcast_llmnr=None,
        broadcast_mdns=None,
    )
    hass.data[DATA_OS_INFO] = OSInfo(
        version=None,
        version_latest=None,
        update_available=False,
        board=None,
        boot=None,
        data_disk=None,
        boot_slots={},
    )
    hass.data[DATA_SUPERVISOR_INFO] = SupervisorInfo(
        version="1.0.0",
        version_latest="1.0.0",
        update_available=False,
        channel=UpdateChannel.STABLE,
        arch="aarch64",
        supported=False,
        healthy=False,
        ip_address=IPv4Address("172.30.32.2"),
        timezone=None,
        logging=LogLevel.INFO,
        debug=False,
        debug_block=False,
        diagnostics=None,
        auto_update=True,
        country=None,
        detect_blocking_io=False,
    )
    hass.data[DATA_NETWORK_INFO] = NetworkInfo(
        interfaces=[],
        docker=DockerNetwork(
            interface="hassio",
            address=IPv4Network("172.30.32.0/23"),
            gateway=IPv4Address("172.30.32.1"),
            dns=IPv4Address("172.30.32.3"),
        ),
        host_internet=None,
        supervisor_internet=False,
    )

    with patch.dict(os.environ, MOCK_ENVIRON):
        info = await get_system_health_info(hass, "hassio")

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info["healthy"] == {
        "error": "Unhealthy",
        "type": "failed",
    }
    assert info["supported"] == {
        "error": "Unsupported",
        "type": "failed",
    }
    assert info["version_api"] == {
        "error": "unreachable",
        "type": "failed",
    }
