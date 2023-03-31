"""The tests for Home Assistant frontend."""
from datetime import timedelta
from http import HTTPStatus
import re
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.frontend import (
    CONF_EXTRA_HTML_URL,
    CONF_EXTRA_HTML_URL_ES5,
    CONF_JS_VERSION,
    CONF_THEMES,
    DEFAULT_THEME_COLOR,
    DOMAIN,
    EVENT_PANELS_UPDATED,
    THEMES_STORAGE_KEY,
)
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from tests.common import MockUser, async_capture_events, async_fire_time_changed
from tests.typing import WebSocketGenerator

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
async def ignore_frontend_deps(hass):
    """Frontend dependencies."""
    frontend = await async_get_integration(hass, "frontend")
    for dep in frontend.dependencies:
        if dep not in ("http", "websocket_api"):
            hass.config.components.add(dep)


@pytest.fixture
async def frontend(hass, ignore_frontend_deps):
    """Frontend setup with themes."""
    assert await async_setup_component(
        hass,
        "frontend",
        {},
    )


@pytest.fixture
async def frontend_themes(hass):
    """Frontend setup with themes."""
    assert await async_setup_component(
        hass,
        "frontend",
        CONFIG_THEMES,
    )


@pytest.fixture
def aiohttp_client(event_loop, aiohttp_client, socket_enabled):
    """Return aiohttp_client and allow opening sockets."""
    return aiohttp_client


@pytest.fixture
async def mock_http_client(hass, aiohttp_client, frontend):
    """Start the Home Assistant HTTP component."""
    return await aiohttp_client(hass.http.app)


@pytest.fixture
async def themes_ws_client(hass, hass_ws_client, frontend_themes):
    """Start the Home Assistant HTTP component."""
    return await hass_ws_client(hass)


@pytest.fixture
async def ws_client(hass, hass_ws_client, frontend):
    """Start the Home Assistant HTTP component."""
    return await hass_ws_client(hass)


@pytest.fixture
async def mock_http_client_with_urls(hass, aiohttp_client, ignore_frontend_deps):
    """Start the Home Assistant HTTP component."""
    assert await async_setup_component(
        hass,
        "frontend",
        {
            DOMAIN: {
                CONF_JS_VERSION: "auto",
                CONF_EXTRA_HTML_URL: ["https://domain.com/my_extra_url.html"],
                CONF_EXTRA_HTML_URL_ES5: ["https://domain.com/my_extra_url_es5.html"],
            }
        },
    )
    return await aiohttp_client(hass.http.app)


@pytest.fixture
def mock_onboarded():
    """Mock that we're onboarded."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded", return_value=True
    ):
        yield


async def test_frontend_and_static(mock_http_client, mock_onboarded) -> None:
    """Test if we can get the frontend."""
    resp = await mock_http_client.get("")
    assert resp.status == 200
    assert "cache-control" not in resp.headers

    text = await resp.text()

    # Test we can retrieve frontend.js
    frontendjs = re.search(r"(?P<app>\/frontend_es5\/app.[A-Za-z0-9]{8}.js)", text)

    assert frontendjs is not None, text
    resp = await mock_http_client.get(frontendjs.groups(0)[0])
    assert resp.status == 200
    assert "public" in resp.headers.get("cache-control")


async def test_dont_cache_service_worker(mock_http_client) -> None:
    """Test that we don't cache the service worker."""
    resp = await mock_http_client.get("/service_worker.js")
    assert resp.status == 200
    assert "cache-control" not in resp.headers


async def test_404(mock_http_client) -> None:
    """Test for HTTP 404 error."""
    resp = await mock_http_client.get("/not-existing")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_we_cannot_POST_to_root(mock_http_client) -> None:
    """Test that POST is not allow to root."""
    resp = await mock_http_client.post("/")
    assert resp.status == 405


async def test_themes_api(hass: HomeAssistant, themes_ws_client) -> None:
    """Test that /api/themes returns correct data."""
    await themes_ws_client.send_json({"id": 5, "type": "frontend/get_themes"})
    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_theme"] == "default"
    assert msg["result"]["default_dark_theme"] is None
    assert msg["result"]["themes"] == MOCK_THEMES

    # safe mode
    hass.config.safe_mode = True
    await themes_ws_client.send_json({"id": 6, "type": "frontend/get_themes"})
    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_theme"] == "safe_mode"
    assert msg["result"]["themes"] == {
        "safe_mode": {"primary-color": "#db4437", "accent-color": "#ffca28"}
    }


async def test_themes_persist(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
    ignore_frontend_deps,
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


async def test_themes_save_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any], frontend_themes
) -> None:
    """Test that theme settings are restores after restart."""

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "happy"}, blocking=True
    )

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "dark", "mode": "dark"}, blocking=True
    )

    # To trigger the call_later
    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=60))
    # To execute the save
    await hass.async_block_till_done()

    assert hass_storage[THEMES_STORAGE_KEY]["data"] == {
        "frontend_default_theme": "happy",
        "frontend_default_dark_theme": "dark",
    }


async def test_themes_set_theme(hass: HomeAssistant, themes_ws_client) -> None:
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
    hass: HomeAssistant, themes_ws_client
) -> None:
    """Test frontend.set_theme service called with wrong name."""

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "wrong"}, blocking=True
    )

    await themes_ws_client.send_json({"id": 5, "type": "frontend/get_themes"})

    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_theme"] == "default"


async def test_themes_set_dark_theme(hass: HomeAssistant, themes_ws_client) -> None:
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


async def test_themes_set_dark_theme_wrong_name(
    hass: HomeAssistant, frontend, themes_ws_client
) -> None:
    """Test frontend.set_theme service called with mode dark and wrong name."""
    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "wrong", "mode": "dark"}, blocking=True
    )

    await themes_ws_client.send_json({"id": 5, "type": "frontend/get_themes"})

    msg = await themes_ws_client.receive_json()

    assert msg["result"]["default_dark_theme"] is None


async def test_themes_reload_themes(
    hass: HomeAssistant, frontend, themes_ws_client
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


async def test_missing_themes(hass: HomeAssistant, ws_client) -> None:
    """Test that themes API works when themes are not defined."""
    await ws_client.send_json({"id": 5, "type": "frontend/get_themes"})

    msg = await ws_client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"]["default_theme"] == "default"
    assert msg["result"]["themes"] == {}


async def test_get_panels(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, mock_http_client
) -> None:
    """Test get_panels command."""
    events = async_capture_events(hass, EVENT_PANELS_UPDATED)

    resp = await mock_http_client.get("/map")
    assert resp.status == HTTPStatus.NOT_FOUND

    hass.components.frontend.async_register_built_in_panel(
        "map", "Map", "mdi:tooltip-account", require_admin=True
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

    hass.components.frontend.async_remove_panel("map")

    resp = await mock_http_client.get("/map")
    assert resp.status == HTTPStatus.NOT_FOUND

    assert len(events) == 2


async def test_get_panels_non_admin(
    hass: HomeAssistant, ws_client, hass_admin_user: MockUser
) -> None:
    """Test get_panels command."""
    hass_admin_user.groups = []

    hass.components.frontend.async_register_built_in_panel(
        "map", "Map", "mdi:tooltip-account", require_admin=True
    )
    hass.components.frontend.async_register_built_in_panel(
        "history", "History", "mdi:history"
    )

    await ws_client.send_json({"id": 5, "type": "get_panels"})

    msg = await ws_client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert "history" in msg["result"]
    assert "map" not in msg["result"]


async def test_get_translations(hass: HomeAssistant, ws_client) -> None:
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
    hass: HomeAssistant, ws_client
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
    hass: HomeAssistant, ws_client
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


async def test_auth_authorize(mock_http_client) -> None:
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
        r"(?P<app>\/frontend_latest\/authorize.[A-Za-z0-9]{8}.js)", text
    )

    assert authorizejs is not None, text
    resp = await mock_http_client.get(authorizejs.groups(0)[0])
    assert resp.status == 200
    assert "public" in resp.headers.get("cache-control")


async def test_get_version(hass: HomeAssistant, ws_client) -> None:
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


async def test_static_paths(hass: HomeAssistant, mock_http_client) -> None:
    """Test static paths."""
    resp = await mock_http_client.get(
        "/.well-known/change-password", allow_redirects=False
    )
    assert resp.status == 302
    assert resp.headers["location"] == "/profile"


async def test_manifest_json(
    hass: HomeAssistant, frontend_themes, mock_http_client
) -> None:
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


async def test_static_path_cache(hass: HomeAssistant, mock_http_client) -> None:
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
