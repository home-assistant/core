"""The tests for Home Assistant frontend."""
from datetime import timedelta
import re

import pytest

from homeassistant.components.frontend import (
    CONF_EXTRA_HTML_URL,
    CONF_EXTRA_HTML_URL_ES5,
    CONF_JS_VERSION,
    CONF_THEMES,
    DOMAIN,
    EVENT_PANELS_UPDATED,
    THEMES_STORAGE_KEY,
)
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.const import HTTP_NOT_FOUND
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from tests.async_mock import patch
from tests.common import async_capture_events, async_fire_time_changed

CONFIG_THEMES = {
    DOMAIN: {
        CONF_THEMES: {
            "happy": {"primary-color": "red"},
            "dark": {"primary-color": "black"},
        }
    }
}


@pytest.fixture
def mock_http_client(hass, aiohttp_client):
    """Start the Home Assistant HTTP component."""
    hass.loop.run_until_complete(async_setup_component(hass, "frontend", {}))
    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@pytest.fixture
def mock_http_client_with_themes(hass, aiohttp_client):
    """Start the Home Assistant HTTP component."""
    hass.loop.run_until_complete(
        async_setup_component(
            hass,
            "frontend",
            {DOMAIN: {CONF_THEMES: {"happy": {"primary-color": "red"}}}},
        )
    )
    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@pytest.fixture
def mock_http_client_with_urls(hass, aiohttp_client):
    """Start the Home Assistant HTTP component."""
    hass.loop.run_until_complete(
        async_setup_component(
            hass,
            "frontend",
            {
                DOMAIN: {
                    CONF_JS_VERSION: "auto",
                    CONF_EXTRA_HTML_URL: ["https://domain.com/my_extra_url.html"],
                    CONF_EXTRA_HTML_URL_ES5: [
                        "https://domain.com/my_extra_url_es5.html"
                    ],
                }
            },
        )
    )
    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@pytest.fixture
def mock_onboarded():
    """Mock that we're onboarded."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded", return_value=True
    ):
        yield


async def test_frontend_and_static(mock_http_client, mock_onboarded):
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


async def test_dont_cache_service_worker(mock_http_client):
    """Test that we don't cache the service worker."""
    resp = await mock_http_client.get("/service_worker.js")
    assert resp.status == 200
    assert "cache-control" not in resp.headers


async def test_404(mock_http_client):
    """Test for HTTP 404 error."""
    resp = await mock_http_client.get("/not-existing")
    assert resp.status == HTTP_NOT_FOUND


async def test_we_cannot_POST_to_root(mock_http_client):
    """Test that POST is not allow to root."""
    resp = await mock_http_client.post("/")
    assert resp.status == 405


async def test_themes_api(hass, hass_ws_client):
    """Test that /api/themes returns correct data."""
    assert await async_setup_component(hass, "frontend", CONFIG_THEMES)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "frontend/get_themes"})
    msg = await client.receive_json()

    assert msg["result"]["default_theme"] == "default"
    assert msg["result"]["default_dark_theme"] is None
    assert msg["result"]["themes"] == {
        "happy": {"primary-color": "red"},
        "dark": {"primary-color": "black"},
    }

    # safe mode
    hass.config.safe_mode = True
    await client.send_json({"id": 6, "type": "frontend/get_themes"})
    msg = await client.receive_json()

    assert msg["result"]["default_theme"] == "safe_mode"
    assert msg["result"]["themes"] == {
        "safe_mode": {"primary-color": "#db4437", "accent-color": "#eeee02"}
    }


async def test_themes_persist(hass, hass_ws_client, hass_storage):
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
    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "frontend/get_themes"})
    msg = await client.receive_json()

    assert msg["result"]["default_theme"] == "happy"
    assert msg["result"]["default_dark_theme"] == "dark"


async def test_themes_save_storage(hass, hass_storage):
    """Test that theme settings are restores after restart."""

    hass_storage[THEMES_STORAGE_KEY] = {
        "key": THEMES_STORAGE_KEY,
        "version": 1,
        "data": {},
    }

    assert await async_setup_component(hass, "frontend", CONFIG_THEMES)

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


async def test_themes_set_theme(hass, hass_ws_client):
    """Test frontend.set_theme service."""
    assert await async_setup_component(hass, "frontend", CONFIG_THEMES)
    client = await hass_ws_client(hass)

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "happy"}, blocking=True
    )

    await client.send_json({"id": 5, "type": "frontend/get_themes"})
    msg = await client.receive_json()

    assert msg["result"]["default_theme"] == "happy"

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "default"}, blocking=True
    )

    await client.send_json({"id": 6, "type": "frontend/get_themes"})
    msg = await client.receive_json()

    assert msg["result"]["default_theme"] == "default"

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "happy"}, blocking=True
    )

    await hass.services.async_call(DOMAIN, "set_theme", {"name": "none"}, blocking=True)

    await client.send_json({"id": 7, "type": "frontend/get_themes"})
    msg = await client.receive_json()

    assert msg["result"]["default_theme"] == "default"


async def test_themes_set_theme_wrong_name(hass, hass_ws_client):
    """Test frontend.set_theme service called with wrong name."""
    assert await async_setup_component(hass, "frontend", CONFIG_THEMES)
    client = await hass_ws_client(hass)

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "wrong"}, blocking=True
    )

    await client.send_json({"id": 5, "type": "frontend/get_themes"})

    msg = await client.receive_json()

    assert msg["result"]["default_theme"] == "default"


async def test_themes_set_dark_theme(hass, hass_ws_client):
    """Test frontend.set_theme service called with dark mode."""
    assert await async_setup_component(hass, "frontend", CONFIG_THEMES)
    client = await hass_ws_client(hass)

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "dark", "mode": "dark"}, blocking=True
    )

    await client.send_json({"id": 5, "type": "frontend/get_themes"})
    msg = await client.receive_json()

    assert msg["result"]["default_dark_theme"] == "dark"

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "default", "mode": "dark"}, blocking=True
    )

    await client.send_json({"id": 6, "type": "frontend/get_themes"})
    msg = await client.receive_json()

    assert msg["result"]["default_dark_theme"] == "default"

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "none", "mode": "dark"}, blocking=True
    )

    await client.send_json({"id": 7, "type": "frontend/get_themes"})
    msg = await client.receive_json()

    assert msg["result"]["default_dark_theme"] is None


async def test_themes_set_dark_theme_wrong_name(hass, hass_ws_client):
    """Test frontend.set_theme service called with mode dark and wrong name."""
    assert await async_setup_component(hass, "frontend", CONFIG_THEMES)
    client = await hass_ws_client(hass)

    await hass.services.async_call(
        DOMAIN, "set_theme", {"name": "wrong", "mode": "dark"}, blocking=True
    )

    await client.send_json({"id": 5, "type": "frontend/get_themes"})

    msg = await client.receive_json()

    assert msg["result"]["default_dark_theme"] is None


async def test_themes_reload_themes(hass, hass_ws_client):
    """Test frontend.reload_themes service."""
    assert await async_setup_component(hass, "frontend", CONFIG_THEMES)
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.frontend.async_hass_config_yaml",
        return_value={DOMAIN: {CONF_THEMES: {"sad": {"primary-color": "blue"}}}},
    ):
        await hass.services.async_call(
            DOMAIN, "set_theme", {"name": "happy"}, blocking=True
        )
        await hass.services.async_call(DOMAIN, "reload_themes", blocking=True)

    await client.send_json({"id": 5, "type": "frontend/get_themes"})

    msg = await client.receive_json()

    assert msg["result"]["themes"] == {"sad": {"primary-color": "blue"}}
    assert msg["result"]["default_theme"] == "default"


async def test_missing_themes(hass, hass_ws_client):
    """Test that themes API works when themes are not defined."""
    await async_setup_component(hass, "frontend", {})

    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "frontend/get_themes"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"]["default_theme"] == "default"
    assert msg["result"]["themes"] == {}


async def test_extra_urls(mock_http_client_with_urls, mock_onboarded):
    """Test that extra urls are loaded."""
    resp = await mock_http_client_with_urls.get("/lovelace?latest")
    assert resp.status == 200
    text = await resp.text()
    assert text.find('href="https://domain.com/my_extra_url.html"') >= 0


async def test_get_panels(hass, hass_ws_client, mock_http_client):
    """Test get_panels command."""
    events = async_capture_events(hass, EVENT_PANELS_UPDATED)

    resp = await mock_http_client.get("/map")
    assert resp.status == HTTP_NOT_FOUND

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
    assert resp.status == HTTP_NOT_FOUND

    assert len(events) == 2


async def test_get_panels_non_admin(hass, hass_ws_client, hass_admin_user):
    """Test get_panels command."""
    hass_admin_user.groups = []
    await async_setup_component(hass, "frontend", {})
    hass.components.frontend.async_register_built_in_panel(
        "map", "Map", "mdi:tooltip-account", require_admin=True
    )
    hass.components.frontend.async_register_built_in_panel(
        "history", "History", "mdi:history"
    )

    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "get_panels"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert "history" in msg["result"]
    assert "map" not in msg["result"]


async def test_get_translations(hass, hass_ws_client):
    """Test get_translations command."""
    await async_setup_component(hass, "frontend", {})
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.frontend.async_get_translations",
        side_effect=lambda hass, lang, category, integration, config_flow: {
            "lang": lang
        },
    ):
        await client.send_json(
            {
                "id": 5,
                "type": "frontend/get_translations",
                "language": "nl",
                "category": "lang",
            }
        )
        msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {"resources": {"lang": "nl"}}


async def test_auth_load(mock_http_client, mock_onboarded):
    """Test auth component loaded by default."""
    resp = await mock_http_client.get("/auth/providers")
    assert resp.status == 200


async def test_onboarding_load(mock_http_client):
    """Test onboarding component loaded by default."""
    resp = await mock_http_client.get("/api/onboarding")
    assert resp.status == 200


async def test_auth_authorize(mock_http_client):
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


async def test_get_version(hass, hass_ws_client):
    """Test get_version command."""
    frontend = await async_get_integration(hass, "frontend")
    cur_version = next(
        req.split("==", 1)[1]
        for req in frontend.requirements
        if req.startswith("home-assistant-frontend==")
    )

    await async_setup_component(hass, "frontend", {})
    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "frontend/get_version"})
    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {"version": cur_version}
