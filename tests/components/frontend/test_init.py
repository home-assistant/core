"""The tests for Home Assistant frontend."""

from asyncio import AbstractEventLoop
from collections.abc import Generator
from http import HTTPStatus
from pathlib import Path
import re
from typing import Any
from unittest.mock import patch

from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.frontend import (
    CONF_EXTRA_JS_URL_ES5,
    CONF_EXTRA_MODULE_URL,
    CONF_THEMES,
    DEFAULT_THEME_COLOR,
    DOMAIN,
    EVENT_PANELS_UPDATED,
    THEMES_STORAGE_KEY,
    add_extra_js_url,
    async_register_built_in_panel,
    async_remove_panel,
    remove_extra_js_url,
)
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from tests.common import MockUser, async_capture_events, async_fire_time_changed
from tests.typing import (
    ClientSessionGenerator,
    MockHAClientWebSocket,
    WebSocketGenerator,
)

MOCK_THEMES = {
    "happy": {"primary-color": "red", "app-header-background-color": "blue"},
    "dark": {"primary-color": "black"},
    "light_only": {
        "primary-color": "blue",
        "modes": {
            "light": {"secondary-color": "black"},
        },
    },
    "dark_only": {
        "primary-color": "blue",
        "modes": {
            "dark": {"secondary-color": "white"},
        },
    },
    "light_and_dark": {
        "primary-color": "blue",
        "modes": {
            "light": {"secondary-color": "black"},
            "dark": {"secondary-color": "white"},
        },
    },
}

CONFIG_THEMES = {DOMAIN: {CONF_THEMES: MOCK_THEMES}}


@pytest.fixture
async def ignore_frontend_deps(hass: HomeAssistant) -> None:
    """Frontend dependencies."""
    frontend = await async_get_integration(hass, "frontend")
    for dep in frontend.dependencies:
        if dep not in ("http", "websocket_api"):
            hass.config.components.add(dep)


@pytest.fixture
async def frontend(hass: HomeAssistant, ignore_frontend_deps: None) -> None:
    """Frontend setup with themes."""
    assert await async_setup_component(
        hass,
        "frontend",
        {},
    )


@pytest.fixture
async def frontend_themes(hass: HomeAssistant) -> None:
    """Frontend setup with themes."""
    assert await async_setup_component(
        hass,
        "frontend",
        CONFIG_THEMES,
    )


@pytest.fixture
def aiohttp_client(
    event_loop: AbstractEventLoop,
    aiohttp_client: ClientSessionGenerator,
    socket_enabled: None,
) -> ClientSessionGenerator:
    """Return aiohttp_client and allow opening sockets."""
    return aiohttp_client


@pytest.fixture
async def mock_http_client(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator, frontend: None
) -> TestClient:
    """Start the Home Assistant HTTP component."""
    return await aiohttp_client(hass.http.app)


@pytest.fixture
async def themes_ws_client(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, frontend_themes: None
) -> MockHAClientWebSocket:
    """Start the Home Assistant HTTP component."""
    return await hass_ws_client(hass)


@pytest.fixture
async def ws_client(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, frontend: None
) -> MockHAClientWebSocket:
    """Start the Home Assistant HTTP component."""
    return await hass_ws_client(hass)


@pytest.fixture
async def mock_http_client_with_extra_js(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    ignore_frontend_deps: None,
) -> TestClient:
    """Start the Home Assistant HTTP component."""
    assert await async_setup_component(
        hass,
        "frontend",
        {
            DOMAIN: {
                CONF_EXTRA_MODULE_URL: ["/local/my_module.js"],
                CONF_EXTRA_JS_URL_ES5: ["/local/my_es5.js"],
            }
        },
    )
    return await aiohttp_client(hass.http.app)


@pytest.fixture
def mock_onboarded() -> Generator[None]:
    """Mock that we're onboarded."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded", return_value=True
    ):
        yield


@pytest.mark.usefixtures("mock_onboarded")
async def test_frontend_and_static(mock_http_client: TestClient) -> None:
    """Test if we can get the frontend."""
    resp = await mock_http_client.get("")
    assert resp.status == 200
    assert "cache-control" not in resp.headers

    text = await resp.text()

    # Test we can retrieve frontend.js
    frontendjs = re.search(r"(?P<app>\/frontend_es5\/app.[A-Za-z0-9_-]{11}.js)", text)

    assert frontendjs is not None, text
    resp = await mock_http_client.get(frontendjs.groups(0)[0])
    assert resp.status == 200
    assert "public" in resp.headers.get("cache-control")


@pytest.mark.parametrize("sw_url", ["/sw-modern.js", "/sw-legacy.js"])
async def test_dont_cache_service_worker(
    mock_http_client: TestClient, sw_url: str
) -> None:
    """Test that we don't cache the service worker."""
    resp = await mock_http_client.get(sw_url)
    assert resp.status == 200
    assert "cache-control" not in resp.headers


async def test_404(mock_http_client: TestClient) -> None:
    """Test for HTTP 404 error."""
    resp = await mock_http_client.get("/not-existing")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_we_cannot_POST_to_root(mock_http_client: TestClient) -> None:
    """Test that POST is not allow to root."""
    resp = await mock_http_client.post("/")
    assert resp.status == 405


async def test_themes_api(
    hass: HomeAssistant, themes_ws_client: MockHAClientWebSocket
) -> None:
    """Test that /api/themes returns correct data."""
    await themes_ws_client.send_json({"id": 5, "type": "frontend/get_themes"})
    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_theme"] == "default"
    assert msg["result"]["default_dark_theme"] is None
    assert msg["result"]["themes"] == MOCK_THEMES

    # recovery mode
    hass.config.recovery_mode = True
    await themes_ws_client.send_json({"id": 6, "type": "frontend/get_themes"})
    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_theme"] == "default"
    assert msg["result"]["themes"] == {}

    # safe mode
    hass.config.recovery_mode = False
    hass.config.safe_mode = True
    await themes_ws_client.send_json({"id": 7, "type": "frontend/get_themes"})
    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_theme"] == "default"
    assert msg["result"]["themes"] == {}


@pytest.mark.usefixtures("ignore_frontend_deps")
async def test_themes_persist(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that theme settings are restores after restart."""
    hass_storage[THEMES_STORAGE_KEY] = {
        "key": THEMES_STORAGE_KEY,
        "version": 1,
        "data": {
            "frontend_default_theme": "happy",
            "frontend_default_dark_theme": "dark",
        },
    }

    assert await async_setup_component(hass, "frontend", CONFIG_THEMES)
    themes_ws_client = await hass_ws_client(hass)

    await themes_ws_client.send_json({"id": 5, "type": "frontend/get_themes"})
    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_theme"] == "happy"
    assert msg["result"]["default_dark_theme"] == "dark"


@pytest.mark.usefixtures("frontend_themes")
async def test_themes_save_storage(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that theme settings are restores after restart."""

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "happy"}, blocking=True
    )

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "dark", "mode": "dark"}, blocking=True
    )

    # To trigger the call_later
    freezer.tick(60.0)
    async_fire_time_changed(hass)
    # To execute the save
    await hass.async_block_till_done()

    assert hass_storage[THEMES_STORAGE_KEY]["data"] == {
        "frontend_default_theme": "happy",
        "frontend_default_dark_theme": "dark",
    }


async def test_themes_set_theme(
    hass: HomeAssistant, themes_ws_client: MockHAClientWebSocket
) -> None:
    """Test frontend.set_theme service."""
    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "happy"}, blocking=True
    )

    await themes_ws_client.send_json({"id": 5, "type": "frontend/get_themes"})
    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_theme"] == "happy"

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "default"}, blocking=True
    )

    await themes_ws_client.send_json({"id": 6, "type": "frontend/get_themes"})
    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_theme"] == "default"

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "happy"}, blocking=True
    )

    await hass.services.async_call(DOMAIN, "set_theme", {"name": "none"}, blocking=True)

    await themes_ws_client.send_json({"id": 7, "type": "frontend/get_themes"})
    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_theme"] == "default"


async def test_themes_set_theme_wrong_name(
    hass: HomeAssistant, themes_ws_client: MockHAClientWebSocket
) -> None:
    """Test frontend.set_theme service called with wrong name."""

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "wrong"}, blocking=True
    )

    await themes_ws_client.send_json({"id": 5, "type": "frontend/get_themes"})

    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_theme"] == "default"


async def test_themes_set_dark_theme(
    hass: HomeAssistant, themes_ws_client: MockHAClientWebSocket
) -> None:
    """Test frontend.set_theme service called with dark mode."""

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "dark", "mode": "dark"}, blocking=True
    )

    await themes_ws_client.send_json({"id": 5, "type": "frontend/get_themes"})
    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_dark_theme"] == "dark"

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "default", "mode": "dark"}, blocking=True
    )

    await themes_ws_client.send_json({"id": 6, "type": "frontend/get_themes"})
    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_dark_theme"] == "default"

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "none", "mode": "dark"}, blocking=True
    )

    await themes_ws_client.send_json({"id": 7, "type": "frontend/get_themes"})
    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_dark_theme"] is None

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "light_and_dark", "mode": "dark"}, blocking=True
    )

    await themes_ws_client.send_json({"id": 8, "type": "frontend/get_themes"})
    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_dark_theme"] == "light_and_dark"


@pytest.mark.usefixtures("frontend")
async def test_themes_set_dark_theme_wrong_name(
    hass: HomeAssistant, themes_ws_client: MockHAClientWebSocket
) -> None:
    """Test frontend.set_theme service called with mode dark and wrong name."""
    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "wrong", "mode": "dark"}, blocking=True
    )

    await themes_ws_client.send_json({"id": 5, "type": "frontend/get_themes"})

    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_dark_theme"] is None


@pytest.mark.usefixtures("frontend")
async def test_themes_reload_themes(
    hass: HomeAssistant, themes_ws_client: MockHAClientWebSocket
) -> None:
    """Test frontend.reload_themes service."""

    with patch(
        "homeassistant.components.frontend.async_hass_config_yaml",
        return_value={DOMAIN: {CONF_THEMES: {"sad": {"primary-color": "blue"}}}},
    ):
        await hass.services.async_call(
            DOMAIN, "set_theme", {"name": "happy"}, blocking=True
        )
        await hass.services.async_call(DOMAIN, "reload_themes", blocking=True)

    await themes_ws_client.send_json({"id": 5, "type": "frontend/get_themes"})

    msg = await themes_ws_client.receive_json()

    assert msg["result"]["themes"] == {"sad": {"primary-color": "blue"}}
    assert msg["result"]["default_theme"] == "default"


async def test_missing_themes(ws_client: MockHAClientWebSocket) -> None:
    """Test that themes API works when themes are not defined."""
    await ws_client.send_json({"id": 5, "type": "frontend/get_themes"})

    msg = await ws_client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"]["default_theme"] == "default"
    assert msg["result"]["themes"] == {}


@pytest.mark.usefixtures("mock_onboarded")
async def test_extra_js(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_http_client_with_extra_js: TestClient,
) -> None:
    """Test that extra javascript is loaded."""

    async def get_response():
        resp = await mock_http_client_with_extra_js.get("")
        assert resp.status == 200
        assert "cache-control" not in resp.headers

        return await resp.text()

    text = await get_response()
    assert '"/local/my_module.js"' in text
    assert '"/local/my_es5.js"' in text

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "frontend/subscribe_extra_js"})
    msg = await client.receive_json()

    assert msg["success"] is True
    subscription_id = msg["id"]

    # Test dynamically adding and removing extra javascript
    add_extra_js_url(hass, "/local/my_module_2.js", False)
    add_extra_js_url(hass, "/local/my_es5_2.js", True)
    text = await get_response()
    assert '"/local/my_module_2.js"' in text
    assert '"/local/my_es5_2.js"' in text

    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["event"] == {
        "change_type": "added",
        "item": {"type": "module", "url": "/local/my_module_2.js"},
    }
    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["event"] == {
        "change_type": "added",
        "item": {"type": "es5", "url": "/local/my_es5_2.js"},
    }

    remove_extra_js_url(hass, "/local/my_module_2.js", False)
    remove_extra_js_url(hass, "/local/my_es5_2.js", True)
    text = await get_response()
    assert '"/local/my_module_2.js"' not in text
    assert '"/local/my_es5_2.js"' not in text

    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["event"] == {
        "change_type": "removed",
        "item": {"type": "module", "url": "/local/my_module_2.js"},
    }
    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["event"] == {
        "change_type": "removed",
        "item": {"type": "es5", "url": "/local/my_es5_2.js"},
    }

    # Remove again should not raise
    remove_extra_js_url(hass, "/local/my_module_2.js", False)
    remove_extra_js_url(hass, "/local/my_es5_2.js", True)
    text = await get_response()
    assert '"/local/my_module_2.js"' not in text
    assert '"/local/my_es5_2.js"' not in text

    # safe mode
    hass.config.safe_mode = True
    text = await get_response()
    assert '"/local/my_module.js"' not in text
    assert '"/local/my_es5.js"' not in text

    # Test dynamically adding extra javascript
    add_extra_js_url(hass, "/local/my_module_2.js", False)
    add_extra_js_url(hass, "/local/my_es5_2.js", True)
    text = await get_response()
    assert '"/local/my_module_2.js"' not in text
    assert '"/local/my_es5_2.js"' not in text


async def test_get_panels(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_http_client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test get_panels command."""
    events = async_capture_events(hass, EVENT_PANELS_UPDATED)

    resp = await mock_http_client.get("/map")
    assert resp.status == HTTPStatus.NOT_FOUND

    async_register_built_in_panel(
        hass, "map", "Map", "mdi:tooltip-account", require_admin=True
    )

    resp = await mock_http_client.get("/map")
    assert resp.status == 200

    assert len(events) == 1

    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "get_panels"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"]["map"]["component_name"] == "map"
    assert msg["result"]["map"]["url_path"] == "map"
    assert msg["result"]["map"]["icon"] == "mdi:tooltip-account"
    assert msg["result"]["map"]["title"] == "Map"
    assert msg["result"]["map"]["require_admin"] is True

    async_remove_panel(hass, "map")

    resp = await mock_http_client.get("/map")
    assert resp.status == HTTPStatus.NOT_FOUND

    assert len(events) == 2

    # Remove again, will warn but not trigger event
    async_remove_panel(hass, "map")
    assert "Removing unknown panel map" in caplog.text
    caplog.clear()

    # Remove again, without warning
    async_remove_panel(hass, "map", warn_if_unknown=False)
    assert "Removing unknown panel map" not in caplog.text


async def test_get_panels_non_admin(
    hass: HomeAssistant, ws_client: MockHAClientWebSocket, hass_admin_user: MockUser
) -> None:
    """Test get_panels command."""
    hass_admin_user.groups = []

    async_register_built_in_panel(
        hass, "map", "Map", "mdi:tooltip-account", require_admin=True
    )
    async_register_built_in_panel(hass, "history", "History", "mdi:history")

    await ws_client.send_json({"id": 5, "type": "get_panels"})

    msg = await ws_client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert "history" in msg["result"]
    assert "map" not in msg["result"]


async def test_get_translations(ws_client: MockHAClientWebSocket) -> None:
    """Test get_translations command."""
    with patch(
        "homeassistant.components.frontend.async_get_translations",
        side_effect=lambda hass, lang, category, integrations, config_flow: {
            "lang": lang
        },
    ):
        await ws_client.send_json(
            {
                "id": 5,
                "type": "frontend/get_translations",
                "language": "nl",
                "category": "lang",
            }
        )
        msg = await ws_client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {"resources": {"lang": "nl"}}


async def test_get_translations_for_integrations(
    ws_client: MockHAClientWebSocket,
) -> None:
    """Test get_translations for integrations command."""
    with patch(
        "homeassistant.components.frontend.async_get_translations",
        side_effect=lambda hass, lang, category, integration, config_flow: {
            "lang": lang,
            "integration": integration,
        },
    ):
        await ws_client.send_json(
            {
                "id": 5,
                "type": "frontend/get_translations",
                "integration": ["frontend", "http"],
                "language": "nl",
                "category": "lang",
            }
        )
        msg = await ws_client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert set(msg["result"]["resources"]["integration"]) == {"frontend", "http"}


async def test_get_translations_for_single_integration(
    ws_client: MockHAClientWebSocket,
) -> None:
    """Test get_translations for integration command."""
    with patch(
        "homeassistant.components.frontend.async_get_translations",
        side_effect=lambda hass, lang, category, integrations, config_flow: {
            "lang": lang,
            "integration": integrations,
        },
    ):
        await ws_client.send_json(
            {
                "id": 5,
                "type": "frontend/get_translations",
                "integration": "http",
                "language": "nl",
                "category": "lang",
            }
        )
        msg = await ws_client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {"resources": {"lang": "nl", "integration": ["http"]}}


async def test_auth_load(hass: HomeAssistant) -> None:
    """Test auth component loaded by default."""
    frontend = await async_get_integration(hass, "frontend")
    assert "auth" in frontend.dependencies


async def test_onboarding_load(hass: HomeAssistant) -> None:
    """Test onboarding component loaded by default."""
    frontend = await async_get_integration(hass, "frontend")
    assert "onboarding" in frontend.dependencies


async def test_auth_authorize(mock_http_client: TestClient) -> None:
    """Test the authorize endpoint works."""
    resp = await mock_http_client.get(
        "/auth/authorize?response_type=code&client_id=https://localhost/&"
        "redirect_uri=https://localhost/&state=123%23456"
    )
    assert resp.status == 200
    # No caching of auth page.
    assert "cache-control" not in resp.headers

    text = await resp.text()

    # Test we can retrieve authorize.js
    authorizejs = re.search(
        r"(?P<app>\/frontend_latest\/authorize.[A-Za-z0-9_-]{11}.js)", text
    )

    assert authorizejs is not None, text
    resp = await mock_http_client.get(authorizejs.groups(0)[0])
    assert resp.status == 200
    assert "public" in resp.headers.get("cache-control")


async def test_get_version(
    hass: HomeAssistant, ws_client: MockHAClientWebSocket
) -> None:
    """Test get_version command."""
    frontend = await async_get_integration(hass, "frontend")
    cur_version = next(
        req.split("==", 1)[1]
        for req in frontend.requirements
        if req.startswith("home-assistant-frontend==")
    )

    await ws_client.send_json({"id": 5, "type": "frontend/get_version"})
    msg = await ws_client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {"version": cur_version}


async def test_static_paths(mock_http_client: TestClient) -> None:
    """Test static paths."""
    resp = await mock_http_client.get(
        "/.well-known/change-password", allow_redirects=False
    )
    assert resp.status == 302
    assert resp.headers["location"] == "/profile"


@pytest.mark.usefixtures("frontend_themes")
async def test_manifest_json(hass: HomeAssistant, mock_http_client: TestClient) -> None:
    """Test for fetching manifest.json."""
    resp = await mock_http_client.get("/manifest.json")
    assert resp.status == HTTPStatus.OK
    assert "cache-control" not in resp.headers

    json = await resp.json()
    assert json["theme_color"] == DEFAULT_THEME_COLOR

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "happy"}, blocking=True
    )
    await hass.async_block_till_done()

    resp = await mock_http_client.get("/manifest.json")
    assert resp.status == HTTPStatus.OK
    assert "cache-control" not in resp.headers

    json = await resp.json()
    assert json["theme_color"] != DEFAULT_THEME_COLOR


async def test_static_path_cache(mock_http_client: TestClient) -> None:
    """Test static paths cache."""
    resp = await mock_http_client.get("/lovelace/default_view", allow_redirects=False)
    assert resp.status == 404

    resp = await mock_http_client.get("/frontend_latest/", allow_redirects=False)
    assert resp.status == 403

    resp = await mock_http_client.get(
        "/static/icons/favicon.ico", allow_redirects=False
    )
    assert resp.status == 200

    # and again to make sure the cache works
    resp = await mock_http_client.get(
        "/static/icons/favicon.ico", allow_redirects=False
    )
    assert resp.status == 200

    resp = await mock_http_client.get(
        "/static/fonts/roboto/Roboto-Bold.woff2", allow_redirects=False
    )
    assert resp.status == 200

    resp = await mock_http_client.get("/static/does-not-exist", allow_redirects=False)
    assert resp.status == 404

    # and again to make sure the cache works
    resp = await mock_http_client.get("/static/does-not-exist", allow_redirects=False)
    assert resp.status == 404


async def test_get_icons(ws_client: MockHAClientWebSocket) -> None:
    """Test get_icons command."""
    with patch(
        "homeassistant.components.frontend.async_get_icons",
        side_effect=lambda hass, category, integrations: {},
    ):
        await ws_client.send_json(
            {
                "id": 5,
                "type": "frontend/get_icons",
                "category": "entity_component",
            }
        )
        msg = await ws_client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {"resources": {}}


async def test_get_icons_for_integrations(ws_client: MockHAClientWebSocket) -> None:
    """Test get_icons for integrations command."""
    with patch(
        "homeassistant.components.frontend.async_get_icons",
        side_effect=lambda hass, category, integrations: {
            integration: {} for integration in integrations
        },
    ):
        await ws_client.send_json(
            {
                "id": 5,
                "type": "frontend/get_icons",
                "integration": ["frontend", "http"],
                "category": "entity",
            }
        )
        msg = await ws_client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert set(msg["result"]["resources"]) == {"frontend", "http"}


async def test_get_icons_for_single_integration(
    ws_client: MockHAClientWebSocket,
) -> None:
    """Test get_icons for integration command."""
    with patch(
        "homeassistant.components.frontend.async_get_icons",
        side_effect=lambda hass, category, integrations: {
            integration: {} for integration in integrations
        },
    ):
        await ws_client.send_json(
            {
                "id": 5,
                "type": "frontend/get_icons",
                "integration": "http",
                "category": "entity",
            }
        )
        msg = await ws_client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {"resources": {"http": {}}}


async def test_www_local_dir(
    hass: HomeAssistant, tmp_path: Path, hass_client: ClientSessionGenerator
) -> None:
    """Test local www folder."""
    hass.config.config_dir = str(tmp_path)
    tmp_path_www = tmp_path / "www"
    x_txt_file = tmp_path_www / "x.txt"

    def _create_www_and_x_txt():
        tmp_path_www.mkdir()
        x_txt_file.write_text("any")

    await hass.async_add_executor_job(_create_www_and_x_txt)

    assert await async_setup_component(hass, "frontend", {})
    client = await hass_client()
    resp = await client.get("/local/x.txt")
    assert resp.status == HTTPStatus.OK
