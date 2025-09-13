"""The tests for the hassio switch."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.hassio import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import MOCK_REPOSITORIES, MOCK_STORE_ADDONS

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_ENVIRON = {"SUPERVISOR": "127.0.0.1", "SUPERVISOR_TOKEN": "abcdefgh"}


@pytest.fixture(autouse=True)
def mock_all(
    aioclient_mock: AiohttpClientMocker,
    addon_installed: AsyncMock,
    store_info: AsyncMock,
    addon_changelog: AsyncMock,
    addon_stats: AsyncMock,
    resolution_info: AsyncMock,
) -> None:
    """Mock all setup requests."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
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
        "http://127.0.0.1/host/info",
        json={
            "result": "ok",
            "data": {
                "result": "ok",
                "data": {
                    "chassis": "vm",
                    "operating_system": "Debian GNU/Linux 10 (buster)",
                    "kernel": "4.19.0-6-amd64",
                },
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/core/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0", "version": "1.0.0"}},
    )
    aioclient_mock.get(
        "http://127.0.0.1/os/info",
        json={
            "result": "ok",
            "data": {
                "version_latest": "1.0.0",
                "version": "1.0.0",
                "update_available": False,
            },
        },
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
                        "update_available": True,
                        "icon": False,
                        "version": "2.0.0",
                        "version_latest": "2.0.1",
                        "repository": "core",
                        "url": "https://github.com/home-assistant/addons/test",
                    },
                    {
                        "name": "test-two",
                        "state": "stopped",
                        "slug": "test-two",
                        "installed": True,
                        "update_available": False,
                        "icon": True,
                        "version": "3.1.0",
                        "version_latest": "3.1.0",
                        "repository": "core",
                        "url": "https://github.com",
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
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels", json={"result": "ok", "data": {"panels": {}}}
    )
    aioclient_mock.get(
        "http://127.0.0.1/network/info",
        json={
            "result": "ok",
            "data": {
                "host_internet": True,
                "supervisor_internet": True,
            },
        },
    )


@pytest.mark.parametrize(
    ("store_addons", "store_repositories"), [(MOCK_STORE_ADDONS, MOCK_REPOSITORIES)]
)
@pytest.mark.parametrize(
    ("entity_id", "expected", "addon_state"),
    [
        ("switch.test", "on", "started"),
        ("switch.test_two", "off", "stopped"),
    ],
)
async def test_switch_state(
    hass: HomeAssistant,
    entity_id: str,
    expected: str,
    addon_state: str,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    addon_installed: AsyncMock,
) -> None:
    """Test hassio addon switch state."""
    addon_installed.return_value.state = addon_state
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

    # Verify that the entity have the expected state.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("store_addons", "store_repositories"), [(MOCK_STORE_ADDONS, MOCK_REPOSITORIES)]
)
async def test_switch_turn_on(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    addon_installed: AsyncMock,
) -> None:
    """Test turning on addon switch."""
    entity_id = "switch.test_two"
    addon_installed.return_value.state = "stopped"

    # Mock the start addon API call
    aioclient_mock.post("http://127.0.0.1/addons/test-two/start", json={"result": "ok"})

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

    # Verify initial state is off
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    # Turn on the switch
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    # Verify the API was called
    assert len(aioclient_mock.mock_calls) > 0
    start_call_found = False
    for call in aioclient_mock.mock_calls:
        if call[1].path == "/addons/test-two/start" and call[0] == "POST":
            start_call_found = True
            break
    assert start_call_found


@pytest.mark.parametrize(
    ("store_addons", "store_repositories"), [(MOCK_STORE_ADDONS, MOCK_REPOSITORIES)]
)
async def test_switch_turn_off(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    addon_installed: AsyncMock,
) -> None:
    """Test turning off addon switch."""
    entity_id = "switch.test"
    addon_installed.return_value.state = "started"

    # Mock the stop addon API call
    aioclient_mock.post("http://127.0.0.1/addons/test/stop", json={"result": "ok"})

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

    # Verify initial state is on
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    # Turn off the switch
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    # Verify the API was called
    assert len(aioclient_mock.mock_calls) > 0
    stop_call_found = False
    for call in aioclient_mock.mock_calls:
        if call[1].path == "/addons/test/stop" and call[0] == "POST":
            stop_call_found = True
            break
    assert stop_call_found
