"""The tests for the hassio component."""
import os

import pytest

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components import frontend
from homeassistant.components.hassio import STORAGE_KEY
from homeassistant.setup import async_setup_component

from tests.async_mock import patch

MOCK_ENVIRON = {"HASSIO": "127.0.0.1", "HASSIO_TOKEN": "abcdefgh"}


@pytest.fixture(autouse=True)
def mock_all(aioclient_mock):
    """Mock all setup requests."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/info",
        json={
            "result": "ok",
            "data": {"supervisor": "222", "homeassistant": "0.110.0", "hassos": None},
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
        "http://127.0.0.1/ingress/panels", json={"result": "ok", "data": {"panels": {}}}
    )


async def test_setup_api_ping(hass, aioclient_mock):
    """Test setup with API ping."""
    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(hass, "hassio", {})
        assert result

    assert aioclient_mock.call_count == 6
    assert hass.components.hassio.get_homeassistant_version() == "0.110.0"
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

    assert aioclient_mock.call_count == 6
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

    assert aioclient_mock.call_count == 6
    assert not aioclient_mock.mock_calls[1][2]["ssl"]
    assert aioclient_mock.mock_calls[1][2]["port"] == 9999
    assert not aioclient_mock.mock_calls[1][2]["watchdog"]


async def test_setup_api_push_api_data_default(hass, aioclient_mock, hass_storage):
    """Test setup with API push default data."""
    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(hass, "hassio", {"http": {}, "hassio": {}})
        assert result

    assert aioclient_mock.call_count == 6
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

    assert aioclient_mock.call_count == 6
    assert not aioclient_mock.mock_calls[1][2]["ssl"]
    assert aioclient_mock.mock_calls[1][2]["port"] == 8123
    assert aioclient_mock.mock_calls[1][2]["refresh_token"] == token.token


async def test_setup_core_push_timezone(hass, aioclient_mock):
    """Test setup with API push default data."""
    hass.config.time_zone = "testzone"

    with patch.dict(os.environ, MOCK_ENVIRON):
        result = await async_setup_component(hass, "hassio", {"hassio": {}})
        assert result

    assert aioclient_mock.call_count == 6
    assert aioclient_mock.mock_calls[2][2]["timezone"] == "testzone"

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

    assert aioclient_mock.call_count == 6
    assert aioclient_mock.mock_calls[-1][3]["X-Hassio-Key"] == "123456"


async def test_fail_setup_without_environ_var(hass):
    """Fail setup if no environ variable set."""
    with patch.dict(os.environ, {}, clear=True):
        result = await async_setup_component(hass, "hassio", {})
        assert not result


async def test_warn_when_cannot_connect(hass, caplog):
    """Fail warn when we cannot connect."""
    with patch.dict(os.environ, MOCK_ENVIRON), patch(
        "homeassistant.components.hassio.HassIO.is_connected", return_value=None,
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
    await hass.services.async_call(
        "hassio", "addon_stdin", {"addon": "test", "input": "test"}
    )
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 7
    assert aioclient_mock.mock_calls[-1][2] == "test"

    await hass.services.async_call("hassio", "host_shutdown", {})
    await hass.services.async_call("hassio", "host_reboot", {})
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 9

    await hass.services.async_call("hassio", "snapshot_full", {})
    await hass.services.async_call(
        "hassio",
        "snapshot_partial",
        {"addons": ["test"], "folders": ["ssl"], "password": "123456"},
    )
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 11
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

    assert aioclient_mock.call_count == 13
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
