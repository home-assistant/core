"""The tests for the hassio update entities."""
import os
from unittest.mock import patch

import pytest

from homeassistant.components.hassio import DOMAIN
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator

MOCK_ENVIRON = {"SUPERVISOR": "127.0.0.1", "SUPERVISOR_TOKEN": "abcdefgh"}


@pytest.fixture(autouse=True)
def mock_all(aioclient_mock, request):
    """Mock all setup requests."""
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
        json={
            "result": "ok",
            "data": {"version_latest": "1.0.0dev222", "version": "1.0.0dev221"},
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/os/info",
        json={
            "result": "ok",
            "data": {
                "version_latest": "1.0.0dev2222",
                "version": "1.0.0dev2221",
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
                "version_latest": "1.0.1dev222",
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
                        "name": "test2",
                        "state": "stopped",
                        "slug": "test2",
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
    ("entity_id", "expected_state", "auto_update"),
    [
        ("update.home_assistant_operating_system_update", "on", False),
        ("update.home_assistant_supervisor_update", "on", True),
        ("update.home_assistant_core_update", "on", False),
        ("update.test_update", "on", True),
        ("update.test2_update", "off", False),
    ],
)
async def test_update_entities(
    hass: HomeAssistant,
    entity_id,
    expected_state,
    auto_update,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test update entities."""
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

    # Verify that the entity have the expected state.
    state = hass.states.get(entity_id)
    assert state.state == expected_state

    # Verify that the auto_update attribute is correct
    assert state.attributes["auto_update"] is auto_update


async def test_update_addon(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test updating addon update entity."""
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

    aioclient_mock.post(
        "http://127.0.0.1/addons/test/update",
        json={"result": "ok", "data": {}},
    )

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": "update.test_update"},
        blocking=True,
    )


async def test_update_os(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test updating OS update entity."""
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

    aioclient_mock.post(
        "http://127.0.0.1/os/update",
        json={"result": "ok", "data": {}},
    )

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": "update.home_assistant_operating_system_update"},
        blocking=True,
    )


async def test_update_core(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test updating core update entity."""
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

    aioclient_mock.post(
        "http://127.0.0.1/core/update",
        json={"result": "ok", "data": {}},
    )

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": "update.home_assistant_os_update"},
        blocking=True,
    )


async def test_update_supervisor(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test updating supervisor update entity."""
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

    aioclient_mock.post(
        "http://127.0.0.1/supervisor/update",
        json={"result": "ok", "data": {}},
    )

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": "update.home_assistant_supervisor_update"},
        blocking=True,
    )


async def test_update_addon_with_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test updating addon update entity with error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
    await hass.async_block_till_done()

    aioclient_mock.post(
        "http://127.0.0.1/addons/test/update",
        exc=HassioAPIError,
    )

    with pytest.raises(HomeAssistantError):
        assert not await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.test_update"},
            blocking=True,
        )


async def test_update_os_with_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test updating OS update entity with error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
    await hass.async_block_till_done()

    aioclient_mock.post(
        "http://127.0.0.1/os/update",
        exc=HassioAPIError,
    )

    with pytest.raises(HomeAssistantError):
        assert not await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.home_assistant_operating_system_update"},
            blocking=True,
        )


async def test_update_supervisor_with_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test updating supervisor update entity with error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
    await hass.async_block_till_done()

    aioclient_mock.post(
        "http://127.0.0.1/supervisor/update",
        exc=HassioAPIError,
    )

    with pytest.raises(HomeAssistantError):
        assert not await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.home_assistant_supervisor_update"},
            blocking=True,
        )


async def test_update_core_with_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test updating core update entity with error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON):
        assert await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
    await hass.async_block_till_done()

    aioclient_mock.post(
        "http://127.0.0.1/core/update",
        exc=HassioAPIError,
    )

    with pytest.raises(HomeAssistantError):
        assert not await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.home_assistant_core_update"},
            blocking=True,
        )


async def test_release_notes_between_versions(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test release notes between versions."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON), patch(
        "homeassistant.components.hassio.get_addons_changelogs",
        return_value={"test": "# 2.0.1\nNew updates\n# 2.0.0\nOld updates"},
    ):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.test_update",
        }
    )
    result = await client.receive_json()
    assert "Old updates" not in result["result"]
    assert "New updates" in result["result"]


async def test_release_notes_full(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test release notes no match."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON), patch(
        "homeassistant.components.hassio.get_addons_changelogs",
        return_value={"test": "# 2.0.0\nNew updates\n# 2.0.0\nOld updates"},
    ):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.test_update",
        }
    )
    result = await client.receive_json()
    assert "Old updates" in result["result"]
    assert "New updates" in result["result"]


async def test_not_release_notes(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test handling where there are no release notes."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    with patch.dict(os.environ, MOCK_ENVIRON), patch(
        "homeassistant.components.hassio.get_addons_changelogs",
        return_value={"test": None},
    ):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.test_update",
        }
    )
    result = await client.receive_json()
    assert result["result"] is None


async def test_no_os_entity(hass: HomeAssistant) -> None:
    """Test handling where there is no os entity."""
    with patch.dict(os.environ, MOCK_ENVIRON), patch(
        "homeassistant.components.hassio.HassIO.get_info",
        return_value={
            "supervisor": "222",
            "homeassistant": "0.110.0",
            "hassos": None,
        },
    ):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result
    await hass.async_block_till_done()

    # Verify that the entity does not exist
    assert not hass.states.get("update.home_assistant_operating_system_update")


async def test_setting_up_core_update_when_addon_fails(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setting up core update when single addon fails."""
    with patch.dict(os.environ, MOCK_ENVIRON), patch(
        "homeassistant.components.hassio.HassIO.get_addon_stats",
        side_effect=HassioAPIError("add-on is not running"),
    ), patch(
        "homeassistant.components.hassio.HassIO.get_addon_changelog",
        side_effect=HassioAPIError("add-on is not running"),
    ), patch(
        "homeassistant.components.hassio.HassIO.get_addon_info",
        side_effect=HassioAPIError("add-on is not running"),
    ):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        await hass.async_block_till_done()
    assert result

    # Verify that the core update entity does exist
    state = hass.states.get("update.home_assistant_core_update")
    assert state
    assert state.state == "on"
    assert "Could not fetch stats for test: add-on is not running" in caplog.text
