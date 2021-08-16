"""Test add-on panel."""
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def mock_all(aioclient_mock):
    """Mock all setup requests."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/homeassistant/info",
        json={"result": "ok", "data": {"last_version": "10.0"}},
    )


async def test_hassio_addon_panel_startup(hass, aioclient_mock, hassio_env):
    """Test startup and panel setup after event."""
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels",
        json={
            "result": "ok",
            "data": {
                "panels": {
                    "test1": {
                        "enable": True,
                        "title": "Test",
                        "icon": "mdi:test",
                        "admin": False,
                    },
                    "test2": {
                        "enable": False,
                        "title": "Test 2",
                        "icon": "mdi:test2",
                        "admin": True,
                    },
                }
            },
        },
    )

    assert aioclient_mock.call_count == 0

    with patch(
        "homeassistant.components.hassio.addon_panel._register_panel",
    ) as mock_panel:
        await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == 3
        assert mock_panel.called
        mock_panel.assert_called_with(
            hass,
            "test1",
            {"enable": True, "title": "Test", "icon": "mdi:test", "admin": False},
        )


async def test_hassio_addon_panel_api(hass, aioclient_mock, hassio_env, hass_client):
    """Test panel api after event."""
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels",
        json={
            "result": "ok",
            "data": {
                "panels": {
                    "test1": {
                        "enable": True,
                        "title": "Test",
                        "icon": "mdi:test",
                        "admin": False,
                    },
                    "test2": {
                        "enable": False,
                        "title": "Test 2",
                        "icon": "mdi:test2",
                        "admin": True,
                    },
                }
            },
        },
    )

    assert aioclient_mock.call_count == 0

    with patch(
        "homeassistant.components.hassio.addon_panel._register_panel",
    ) as mock_panel:
        await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == 3
        assert mock_panel.called
        mock_panel.assert_called_with(
            hass,
            "test1",
            {"enable": True, "title": "Test", "icon": "mdi:test", "admin": False},
        )

        hass_client = await hass_client()

        resp = await hass_client.post("/api/hassio_push/panel/test2")
        assert resp.status == 400

        resp = await hass_client.post("/api/hassio_push/panel/test1")
        assert resp.status == 200
        assert mock_panel.call_count == 2

        mock_panel.assert_called_with(
            hass,
            "test1",
            {"enable": True, "title": "Test", "icon": "mdi:test", "admin": False},
        )
