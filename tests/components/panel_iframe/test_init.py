"""The tests for the panel_iframe component."""

from typing import Any

import pytest

from homeassistant.components.panel_iframe import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator

TEST_CONFIG = {
    "router": {
        "icon": "mdi:network-wireless",
        "title": "Router",
        "url": "http://192.168.1.1",
        "require_admin": True,
    },
    "weather": {
        "icon": "mdi:weather",
        "title": "Weather",
        "url": "https://www.wunderground.com/us/ca/san-diego",
        "require_admin": True,
    },
    "api": {"icon": "mdi:weather", "title": "Api", "url": "/api"},
    "ftp": {
        "icon": "mdi:weather",
        "title": "FTP",
        "url": "ftp://some/ftp",
    },
}


@pytest.mark.parametrize(
    "config_to_try",
    [
        {"invalid space": {"url": "https://home-assistant.io"}},
        {"router": {"url": "not-a-url"}},
    ],
)
async def test_wrong_config(hass: HomeAssistant, config_to_try) -> None:
    """Test setup with wrong configuration."""
    assert not await async_setup_component(
        hass, "panel_iframe", {"panel_iframe": config_to_try}
    )


async def test_import_config(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test import config."""
    client = await hass_ws_client(hass)

    assert await async_setup_component(
        hass,
        "panel_iframe",
        {"panel_iframe": TEST_CONFIG},
    )

    # List dashboards
    await client.send_json_auto_id({"type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "icon": "mdi:network-wireless",
            "id": "router",
            "mode": "storage",
            "require_admin": True,
            "show_in_sidebar": True,
            "title": "Router",
            "url_path": "router",
        },
        {
            "icon": "mdi:weather",
            "id": "weather",
            "mode": "storage",
            "require_admin": True,
            "show_in_sidebar": True,
            "title": "Weather",
            "url_path": "weather",
        },
        {
            "icon": "mdi:weather",
            "id": "api",
            "mode": "storage",
            "require_admin": False,
            "show_in_sidebar": True,
            "title": "Api",
            "url_path": "api",
        },
        {
            "icon": "mdi:weather",
            "id": "ftp",
            "mode": "storage",
            "require_admin": False,
            "show_in_sidebar": True,
            "title": "FTP",
            "url_path": "ftp",
        },
    ]

    for url_path in ("api", "ftp", "router", "weather"):
        await client.send_json_auto_id(
            {"type": "lovelace/config", "url_path": url_path}
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == {
            "strategy": {"type": "iframe", "url": TEST_CONFIG[url_path]["url"]}
        }

    assert hass_storage[DOMAIN]["data"] == {"migrated": True}


async def test_import_config_once(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test import config only happens once."""
    client = await hass_ws_client(hass)

    hass_storage[DOMAIN] = {
        "version": 1,
        "minor_version": 1,
        "key": "map",
        "data": {"migrated": True},
    }

    assert await async_setup_component(
        hass,
        "panel_iframe",
        {"panel_iframe": TEST_CONFIG},
    )

    # List dashboards
    await client.send_json_auto_id({"type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []


async def test_create_issue_when_manually_configured(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test creating issue registry issues."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
