"""Test add-on panel."""

from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def mock_all(
    aioclient_mock: AiohttpClientMocker, supervisor_is_connected: AsyncMock
) -> None:
    """Mock all setup requests."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/homeassistant/info",
        json={"result": "ok", "data": {"last_version": "10.0"}},
    )


@pytest.mark.usefixtures("hassio_env")
async def test_hassio_addon_panel_startup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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


@pytest.mark.usefixtures("hassio_env")
async def test_hassio_addon_panel_api(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
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
        assert resp.status == HTTPStatus.BAD_REQUEST

        resp = await hass_client.post("/api/hassio_push/panel/test1")
        assert resp.status == HTTPStatus.OK
        assert mock_panel.call_count == 2

        mock_panel.assert_called_with(
            hass,
            "test1",
            {"enable": True, "title": "Test", "icon": "mdi:test", "admin": False},
        )


@pytest.mark.usefixtures("hassio_env")
async def test_hassio_addon_panel_registration(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test panel registration calls frontend.async_register_built_in_panel."""
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels",
        json={
            "result": "ok",
            "data": {
                "panels": {
                    "test_addon": {
                        "enable": True,
                        "title": "Test Addon",
                        "icon": "mdi:test-tube",
                        "admin": True,
                    },
                }
            },
        },
    )

    with patch(
        "homeassistant.components.hassio.addon_panel.frontend.async_register_built_in_panel"
    ) as mock_register:
        await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()

        # Verify that async_register_built_in_panel was called with correct arguments
        # for our test addon
        mock_register.assert_any_call(
            hass,
            "app",
            frontend_url_path="test_addon",
            sidebar_title="Test Addon",
            sidebar_icon="mdi:test-tube",
            require_admin=True,
            config={"addon": "test_addon"},
        )
