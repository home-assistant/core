"""The tests for the hassio component."""
import os
from unittest.mock import patch

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components import frontend
<<<<<<< HEAD
from homeassistant.components.hassio import STORAGE_KEY
=======
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.hassio import ADDONS_COORDINATOR, DOMAIN, STORAGE_KEY
from homeassistant.components.hassio.const import (
    ATTR_DATA,
    ATTR_ENDPOINT,
    ATTR_METHOD,
    EVENT_SUPERVISOR_EVENT,
    WS_ID,
    WS_TYPE,
    WS_TYPE_API,
    WS_TYPE_EVENT,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
>>>>>>> 87c3c833a6 (add entry setup and unload test and fix update coordinator)
from homeassistant.setup import async_setup_component

from . import mock_all  # noqa


from tests.common import MockConfigEntry

MOCK_ENVIRON = {"HASSIO": "127.0.0.1", "HASSIO_TOKEN": "abcdefgh"}


async def test_setup_api_ping(hass, aioclient_mock):
    """Test setup with API ping."""
    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(hass, "hassio", {})
        assert result

    assert aioclient_mock.call_count == 9
    assert hass.components.hassio.get_core_info()["version_latest"] == "1.0.0"
    assert hass.components.hassio.is_hassio()


async def test_setup_api_panel(hass, aioclient_mock):
    """Test setup with API ping."""
    assert await async_setup_component(hass, "frontend", {})
    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(hass, "hassio", {})
        assert result

    panels = hass.data[frontend.DATA_PANELS]

    assert panels.get("hassio").to_response() == {
        "component_name": "custom",
        "icon": "hass:home-assistant",
        "title": "Supervisor",
        "url_path": "hassio",
        "require_admin": True,
        "config": {
            "_panel_custom": {
                "embed_iframe": True,
                "js_url": "/api/hassio/app/entrypoint.js",
                "name": "hassio-main",
                "trust_external": False,
            }
        },
    }


async def test_setup_api_push_api_data(hass, aioclient_mock):
    """Test setup with API push."""
    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass, "hassio", {"http": {"server_port": 9999}, "hassio": {}}
        )
        assert result

    assert aioclient_mock.call_count == 9
    assert not aioclient_mock.mock_calls[1][2]["ssl"]
    assert aioclient_mock.mock_calls[1][2]["port"] == 9999
    assert aioclient_mock.mock_calls[1][2]["watchdog"]


async def test_setup_api_push_api_data_server_host(hass, aioclient_mock):
    """Test setup with API push with active server host."""
    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(
            hass,
            "hassio",
            {"http": {"server_port": 9999, "server_host": "127.0.0.1"}, "hassio": {}},
        )
        assert result

    assert aioclient_mock.call_count == 9
    assert not aioclient_mock.mock_calls[1][2]["ssl"]
    assert aioclient_mock.mock_calls[1][2]["port"] == 9999
    assert not aioclient_mock.mock_calls[1][2]["watchdog"]


async def test_setup_api_push_api_data_default(hass, aioclient_mock, hass_storage):
    """Test setup with API push default data."""
    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(hass, "hassio", {"http": {}, "hassio": {}})
        assert result

    assert aioclient_mock.call_count == 9
    assert not aioclient_mock.mock_calls[1][2]["ssl"]
    assert aioclient_mock.mock_calls[1][2]["port"] == 8123
    refresh_token = aioclient_mock.mock_calls[1][2]["refresh_token"]
    hassio_user = await hass.auth.async_get_user(
        hass_storage[STORAGE_KEY]["data"]["hassio_user"]
    )
    assert hassio_user is not None
    assert hassio_user.system_generated
    assert len(hassio_user.groups) == 1
    assert hassio_user.groups[0].id == GROUP_ID_ADMIN
    for token in hassio_user.refresh_tokens.values():
        if token.token == refresh_token:
            break
    else:
        assert False, "refresh token not found"


async def test_setup_adds_admin_group_to_user(hass, aioclient_mock, hass_storage):
    """Test setup with API push default data."""
    # Create user without admin
    user = await hass.auth.async_create_system_user("Hass.io")
    assert not user.is_admin
    await hass.auth.async_create_refresh_token(user)

    hass_storage[STORAGE_KEY] = {
        "data": {"hassio_user": user.id},
        "key": STORAGE_KEY,
        "version": 1,
    }

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(hass, "hassio", {"http": {}, "hassio": {}})
        assert result

    assert user.is_admin


async def test_setup_api_existing_hassio_user(hass, aioclient_mock, hass_storage):
    """Test setup with API push default data."""
    user = await hass.auth.async_create_system_user("Hass.io test")
    token = await hass.auth.async_create_refresh_token(user)
    hass_storage[STORAGE_KEY] = {"version": 1, "data": {"hassio_user": user.id}}
    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(hass, "hassio", {"http": {}, "hassio": {}})
        assert result

    assert aioclient_mock.call_count == 9
    assert not aioclient_mock.mock_calls[1][2]["ssl"]
    assert aioclient_mock.mock_calls[1][2]["port"] == 8123
    assert aioclient_mock.mock_calls[1][2]["refresh_token"] == token.token


async def test_setup_core_push_timezone(hass, aioclient_mock):
    """Test setup with API push default data."""
    hass.config.time_zone = "testzone"

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(hass, "hassio", {"hassio": {}})
        assert result

    assert aioclient_mock.call_count == 9
    assert aioclient_mock.mock_calls[2][2]["timezone"] == "testzone"

    with patch("homeassistant.util.dt.set_default_time_zone"):
        await hass.config.async_update(time_zone="America/New_York")
    await hass.async_block_till_done()
    assert aioclient_mock.mock_calls[-1][2]["timezone"] == "America/New_York"


async def test_setup_hassio_no_additional_data(hass, aioclient_mock):
    """Test setup with API push default data."""
    with patch.dict(os.environ, MOCK_ENVIRON), patch.dict(
        os.environ, {"HASSIO_TOKEN": "123456"}
    ):
        result = await async_setup_component(hass, "hassio", {"hassio": {}})
        assert result

    assert aioclient_mock.call_count == 9
    assert aioclient_mock.mock_calls[-1][3]["X-Hassio-Key"] == "123456"


async def test_fail_setup_without_environ_var(hass):
    """Fail setup if no environ variable set."""
    with patch.dict(os.environ, {}, clear=True):
        result = await async_setup_component(hass, "hassio", {})
        assert not result


async def test_warn_when_cannot_connect(hass, caplog):
    """Fail warn when we cannot connect."""
    with patch.dict(os.environ, MOCK_ENVIRON), patch(
        "homeassistant.components.hassio.HassIO.is_connected",
        return_value=None,
    ):
        result = await async_setup_component(hass, "hassio", {})
        assert result

    assert hass.components.hassio.is_hassio()
    assert "Not connected with Hass.io / system too busy!" in caplog.text


async def test_service_register(hassio_env, hass):
    """Check if service will be setup."""
    assert await async_setup_component(hass, "hassio", {})
    assert hass.services.has_service("hassio", "addon_start")
    assert hass.services.has_service("hassio", "addon_stop")
    assert hass.services.has_service("hassio", "addon_restart")
    assert hass.services.has_service("hassio", "addon_update")
    assert hass.services.has_service("hassio", "addon_stdin")
    assert hass.services.has_service("hassio", "host_shutdown")
    assert hass.services.has_service("hassio", "host_reboot")
    assert hass.services.has_service("hassio", "host_reboot")
    assert hass.services.has_service("hassio", "snapshot_full")
    assert hass.services.has_service("hassio", "snapshot_partial")
    assert hass.services.has_service("hassio", "restore_full")
    assert hass.services.has_service("hassio", "restore_partial")


async def test_service_calls(hassio_env, hass, aioclient_mock):
    """Call service and check the API calls behind that."""
    assert await async_setup_component(hass, "hassio", {})

    aioclient_mock.post("http://127.0.0.1/addons/test/start", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/addons/test/stop", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/addons/test/restart", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/addons/test/update", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/addons/test/stdin", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/host/shutdown", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/host/reboot", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/snapshots/new/full", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/snapshots/new/partial", json={"result": "ok"})
    aioclient_mock.post(
        "http://127.0.0.1/snapshots/test/restore/full", json={"result": "ok"}
    )
    aioclient_mock.post(
        "http://127.0.0.1/snapshots/test/restore/partial", json={"result": "ok"}
    )

    await hass.services.async_call("hassio", "addon_start", {"addon": "test"})
    await hass.services.async_call("hassio", "addon_stop", {"addon": "test"})
    await hass.services.async_call("hassio", "addon_restart", {"addon": "test"})
    await hass.services.async_call("hassio", "addon_update", {"addon": "test"})
    await hass.services.async_call(
        "hassio", "addon_stdin", {"addon": "test", "input": "test"}
    )
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 8
    assert aioclient_mock.mock_calls[-1][2] == "test"

    await hass.services.async_call("hassio", "host_shutdown", {})
    await hass.services.async_call("hassio", "host_reboot", {})
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 10

    await hass.services.async_call("hassio", "snapshot_full", {})
    await hass.services.async_call(
        "hassio",
        "snapshot_partial",
        {"addons": ["test"], "folders": ["ssl"], "password": "123456"},
    )
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 12
    assert aioclient_mock.mock_calls[-1][2] == {
        "addons": ["test"],
        "folders": ["ssl"],
        "password": "123456",
    }

    await hass.services.async_call("hassio", "restore_full", {"snapshot": "test"})
    await hass.services.async_call(
        "hassio",
        "restore_partial",
        {
            "snapshot": "test",
            "homeassistant": False,
            "addons": ["test"],
            "folders": ["ssl"],
            "password": "123456",
        },
    )
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 14
    assert aioclient_mock.mock_calls[-1][2] == {
        "addons": ["test"],
        "folders": ["ssl"],
        "homeassistant": False,
        "password": "123456",
    }


async def test_service_calls_core(hassio_env, hass, aioclient_mock):
    """Call core service and check the API calls behind that."""
    assert await async_setup_component(hass, "hassio", {})

    aioclient_mock.post("http://127.0.0.1/homeassistant/restart", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/homeassistant/stop", json={"result": "ok"})

    await hass.services.async_call("homeassistant", "stop")
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 4

    await hass.services.async_call("homeassistant", "check_config")
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 4

    with patch(
        "homeassistant.config.async_check_ha_config_file", return_value=None
    ) as mock_check_config:
        await hass.services.async_call("homeassistant", "restart")
        await hass.async_block_till_done()
        assert mock_check_config.called

    assert aioclient_mock.call_count == 5


async def test_websocket_supervisor_event(
    hassio_env, hass: HomeAssistant, hass_ws_client
):
    """Test Supervisor websocket event."""
    assert await async_setup_component(hass, "hassio", {})
    websocket_client = await hass_ws_client(hass)

    test_event = async_capture_events(hass, EVENT_SUPERVISOR_EVENT)

    await websocket_client.send_json(
        {WS_ID: 1, WS_TYPE: WS_TYPE_EVENT, ATTR_DATA: {"event": "test"}}
    )

    assert await websocket_client.receive_json()
    await hass.async_block_till_done()

    assert test_event[0].data == {"event": "test"}


async def test_websocket_supervisor_api(
    hassio_env, hass: HomeAssistant, hass_ws_client, aioclient_mock
):
    """Test Supervisor websocket api."""
    assert await async_setup_component(hass, "hassio", {})
    websocket_client = await hass_ws_client(hass)
    aioclient_mock.post(
        "http://127.0.0.1/snapshots/new/partial",
        json={"result": "ok", "data": {"slug": "sn_slug"}},
    )

    await websocket_client.send_json(
        {
            WS_ID: 1,
            WS_TYPE: WS_TYPE_API,
            ATTR_ENDPOINT: "/snapshots/new/partial",
            ATTR_METHOD: "post",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["result"]["slug"] == "sn_slug"

    await websocket_client.send_json(
        {
            WS_ID: 2,
            WS_TYPE: WS_TYPE_API,
            ATTR_ENDPOINT: "/supervisor/info",
            ATTR_METHOD: "get",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["result"]["version_latest"] == "1.0.0"


async def test_entry_load_and_unload(hass, aioclient_mock):
    """Test loading and unloading config entry."""
    aioclient_mock.get(
        "http://127.0.0.1/addons",
        json={
            "result": "ok",
            "data": {
                "addons": [
                    {
                        "name": "test",
                        "slug": "test",
                        "installed": True,
                        "version": "1.0.0",
                        "version_latest": "1.0.0",
                        "url": "https://github.com/home-assistant/addons/test",
                    },
                    {
                        "name": "test2",
                        "slug": "test2",
                        "installed": False,
                        "version": "1.0.0",
                        "version_latest": "1.0.0",
                        "url": "https://github.com/home-assistant/addons/test2",
                    },
                ]
            },
        },
    )

    with patch.dict(os.environ, MOCK_ENVIRON):
        config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert SENSOR_DOMAIN in hass.config.components
    assert BINARY_SENSOR_DOMAIN in hass.config.components
    assert ADDONS_COORDINATOR in hass.data

    assert await config_entry.async_unload(hass)
    await hass.async_block_till_done()
    assert ADDONS_COORDINATOR not in hass.data
