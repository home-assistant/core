"""The tests for the hassio sensors."""
from datetime import timedelta
import os
from unittest.mock import patch

import pytest

from homeassistant.components.hassio import (
    DOMAIN,
    HASSIO_UPDATE_INTERVAL,
    HassioAPIError,
)
from homeassistant.components.hassio.const import REQUEST_REFRESH_DELAY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_ENVIRON = {"SUPERVISOR": "127.0.0.1", "SUPERVISOR_TOKEN": "abcdefgh"}


@pytest.fixture(autouse=True)
def mock_all(aioclient_mock: AiohttpClientMocker, request):
    """Mock all setup requests."""
    _install_default_mocks(aioclient_mock)
    _install_test_addon_stats_mock(aioclient_mock)


def _install_test_addon_stats_mock(aioclient_mock: AiohttpClientMocker):
    """Install mock to provide valid stats for the test addon."""
    aioclient_mock.get(
        "http://127.0.0.1/addons/test/stats",
        json={
            "result": "ok",
            "data": {
                "cpu_percent": 0.99,
                "memory_usage": 182611968,
                "memory_limit": 3977146368,
                "memory_percent": 4.59,
                "network_rx": 362570232,
                "network_tx": 82374138,
                "blk_read": 46010945536,
                "blk_write": 15051526144,
            },
        },
    )


def _install_test_addon_stats_failure_mock(aioclient_mock: AiohttpClientMocker):
    """Install mocks to raise an exception when fetching stats for the test addon."""
    aioclient_mock.get(
        "http://127.0.0.1/addons/test/stats",
        exc=HassioAPIError,
    )


def _install_default_mocks(aioclient_mock: AiohttpClientMocker):
    """Install default mocks."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/info",
        json={
            "result": "ok",
            "data": {
                "supervisor": "222",
                "homeassistant": "0.110.0",
                "hassos": "1.2.3",
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/store",
        json={
            "result": "ok",
            "data": {"addons": [], "repositories": []},
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/host/info",
        json={
            "result": "ok",
            "data": {
                "agent_version": "1.0.0",
                "chassis": "vm",
                "operating_system": "Debian GNU/Linux 10 (buster)",
                "kernel": "4.19.0-6-amd64",
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/core/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0", "version": "1.0.0"}},
    )
    aioclient_mock.get(
        "http://127.0.0.1/os/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0", "version": "1.0.0"}},
    )
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/info",
        json={
            "result": "ok",
            "data": {
                "result": "ok",
                "version": "1.0.0",
                "version_latest": "1.0.0",
                "auto_update": True,
                "addons": [
                    {
                        "name": "test",
                        "state": "started",
                        "slug": "test",
                        "installed": True,
                        "update_available": False,
                        "version": "2.0.0",
                        "version_latest": "2.0.1",
                        "repository": "core",
                        "url": "https://github.com/home-assistant/addons/test",
                        "icon": False,
                    },
                    {
                        "name": "test2",
                        "state": "stopped",
                        "slug": "test2",
                        "installed": True,
                        "update_available": False,
                        "version": "3.1.0",
                        "version_latest": "3.2.0",
                        "repository": "core",
                        "url": "https://github.com",
                        "icon": False,
                    },
                ],
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/core/stats",
        json={
            "result": "ok",
            "data": {
                "cpu_percent": 0.99,
                "memory_usage": 182611968,
                "memory_limit": 3977146368,
                "memory_percent": 4.59,
                "network_rx": 362570232,
                "network_tx": 82374138,
                "blk_read": 46010945536,
                "blk_write": 15051526144,
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/stats",
        json={
            "result": "ok",
            "data": {
                "cpu_percent": 0.99,
                "memory_usage": 182611968,
                "memory_limit": 3977146368,
                "memory_percent": 4.59,
                "network_rx": 362570232,
                "network_tx": 82374138,
                "blk_read": 46010945536,
                "blk_write": 15051526144,
            },
        },
    )
    aioclient_mock.get("http://127.0.0.1/addons/test/changelog", text="")
    aioclient_mock.get(
        "http://127.0.0.1/addons/test/info",
        json={"result": "ok", "data": {"auto_update": True}},
    )
    aioclient_mock.get("http://127.0.0.1/addons/test2/changelog", text="")
    aioclient_mock.get(
        "http://127.0.0.1/addons/test2/info",
        json={"result": "ok", "data": {"auto_update": False}},
    )
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels", json={"result": "ok", "data": {"panels": {}}}
    )
    aioclient_mock.post("http://127.0.0.1/refresh_updates", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/resolution/info",
        json={
            "result": "ok",
            "data": {
                "unsupported": [],
                "unhealthy": [],
                "suggestions": [],
                "issues": [],
                "checks": [],
            },
        },
    )


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        ("sensor.home_assistant_operating_system_version", "1.0.0"),
        ("sensor.home_assistant_operating_system_newest_version", "1.0.0"),
        ("sensor.home_assistant_host_os_agent_version", "1.0.0"),
        ("sensor.home_assistant_core_cpu_percent", "0.99"),
        ("sensor.home_assistant_supervisor_cpu_percent", "0.99"),
        ("sensor.test_version", "2.0.0"),
        ("sensor.test_newest_version", "2.0.1"),
        ("sensor.test2_version", "3.1.0"),
        ("sensor.test2_newest_version", "3.2.0"),
        ("sensor.test_cpu_percent", "0.99"),
        ("sensor.test2_cpu_percent", "unavailable"),
        ("sensor.test_memory_percent", "4.59"),
        ("sensor.test2_memory_percent", "unavailable"),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    entity_id,
    expected,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test hassio OS and addons sensor."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await hass.async_block_till_done()

    # Verify that the entity is disabled by default.
    assert hass.states.get(entity_id) is None

    # Enable the entity.
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # There is a REQUEST_REFRESH_DELAYs cooldown on the debouncer
    async_fire_time_changed(
        hass, dt_util.now() + timedelta(seconds=REQUEST_REFRESH_DELAY)
    )
    await hass.async_block_till_done()

    # Verify that the entity have the expected state.
    state = hass.states.get(entity_id)
    assert state.state == expected


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        ("sensor.test_cpu_percent", "0.99"),
        ("sensor.test_memory_percent", "4.59"),
    ],
)
async def test_stats_addon_sensor(
    hass: HomeAssistant,
    entity_id,
    expected,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test stats addons sensor."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await hass.async_block_till_done()

    # Verify that the entity is disabled by default.
    assert hass.states.get(entity_id) is None

    aioclient_mock.clear_requests()
    _install_default_mocks(aioclient_mock)
    _install_test_addon_stats_failure_mock(aioclient_mock)

    async_fire_time_changed(
        hass, dt_util.utcnow() + HASSIO_UPDATE_INTERVAL + timedelta(seconds=1)
    )
    await hass.async_block_till_done()

    assert "Could not fetch stats" not in caplog.text

    aioclient_mock.clear_requests()
    _install_default_mocks(aioclient_mock)
    _install_test_addon_stats_mock(aioclient_mock)

    async_fire_time_changed(
        hass, dt_util.utcnow() + HASSIO_UPDATE_INTERVAL + timedelta(seconds=1)
    )
    await hass.async_block_till_done()

    # Enable the entity.
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # There is a REQUEST_REFRESH_DELAYs cooldown on the debouncer
    async_fire_time_changed(
        hass, dt_util.now() + timedelta(seconds=REQUEST_REFRESH_DELAY)
    )
    await hass.async_block_till_done()

    # Verify that the entity have the expected state.
    state = hass.states.get(entity_id)
    assert state.state == expected

    aioclient_mock.clear_requests()
    _install_default_mocks(aioclient_mock)
    _install_test_addon_stats_failure_mock(aioclient_mock)

    async_fire_time_changed(
        hass, dt_util.utcnow() + HASSIO_UPDATE_INTERVAL + timedelta(seconds=1)
    )
    await hass.async_block_till_done()

    assert "Could not fetch stats" in caplog.text
