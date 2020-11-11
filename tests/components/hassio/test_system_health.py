"""Test hassio system health."""
import asyncio
import os

from aiohttp import ClientError

from homeassistant.setup import async_setup_component

from .test_init import MOCK_ENVIRON

from tests.async_mock import patch
from tests.common import get_system_health_info


async def test_hassio_system_health(hass, aioclient_mock):
    """Test hassio system health."""
    aioclient_mock.get("http://127.0.0.1/info", json={"result": "ok", "data": {}})
    aioclient_mock.get("http://127.0.0.1/host/info", json={"result": "ok", "data": {}})
    aioclient_mock.get("http://127.0.0.1/os/info", json={"result": "ok", "data": {}})
    aioclient_mock.get("http://127.0.0.1/supervisor/ping", text="")
    aioclient_mock.get("https://version.home-assistant.io/stable.json", text="")
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/info", json={"result": "ok", "data": {}}
    )

    hass.config.components.add("hassio")
    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await async_setup_component(hass, "system_health", {})

    hass.data["hassio_info"] = {
        "channel": "stable",
        "supervisor": "2020.11.1",
        "docker": "19.0.3",
        "hassos": True,
    }
    hass.data["hassio_host_info"] = {
        "operating_system": "Home Assistant OS 5.9",
        "disk_total": "32.0",
        "disk_used": "30.0",
    }
    hass.data["hassio_os_info"] = {"board": "odroid-n2"}
    hass.data["hassio_supervisor_info"] = {
        "healthy": True,
        "supported": True,
        "addons": [{"name": "Awesome Addon", "version": "1.0.0"}],
    }

    info = await get_system_health_info(hass, "hassio")

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info == {
        "board": "odroid-n2",
        "disk_total": "32.0 GB",
        "disk_used": "30.0 GB",
        "docker_version": "19.0.3",
        "healthy": True,
        "host_os": "Home Assistant OS 5.9",
        "installed_addons": "Awesome Addon (1.0.0)",
        "supervisor_api": "ok",
        "supervisor_version": "2020.11.1",
        "supported": True,
        "update_channel": "stable",
        "version_api": "ok",
    }


async def test_hassio_system_health_with_issues(hass, aioclient_mock):
    """Test hassio system health."""
    aioclient_mock.get("http://127.0.0.1/info", json={"result": "ok", "data": {}})
    aioclient_mock.get("http://127.0.0.1/host/info", json={"result": "ok", "data": {}})
    aioclient_mock.get("http://127.0.0.1/os/info", json={"result": "ok", "data": {}})
    aioclient_mock.get("http://127.0.0.1/supervisor/ping", text="")
    aioclient_mock.get("https://version.home-assistant.io/stable.json", exc=ClientError)
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/info", json={"result": "ok", "data": {}}
    )

    hass.config.components.add("hassio")
    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await async_setup_component(hass, "system_health", {})

    hass.data["hassio_info"] = {"channel": "stable"}
    hass.data["hassio_host_info"] = {}
    hass.data["hassio_os_info"] = {}
    hass.data["hassio_supervisor_info"] = {
        "healthy": False,
        "supported": False,
    }

    info = await get_system_health_info(hass, "hassio")

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info["healthy"] == {
        "error": "Unhealthy",
        "more_info": "/hassio/system",
        "type": "failed",
    }
    assert info["supported"] == {
        "error": "Unsupported",
        "more_info": "/hassio/system",
        "type": "failed",
    }
    assert info["version_api"] == {
        "error": "unreachable",
        "more_info": "/hassio/system",
        "type": "failed",
    }
