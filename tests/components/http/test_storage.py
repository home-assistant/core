"""Tests for the HTTP integration user-config storage and YAML migration."""

from ipaddress import ip_network
from typing import Any
from unittest.mock import ANY, Mock, patch

import pytest

from homeassistant.components.http.storage import (
    USER_CONFIG_STORAGE_KEY,
    USER_CONFIG_STORAGE_VERSION,
    to_stored,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def disable_http_server(socket_enabled: None) -> None:
    """Allow the HTTP server to start."""
    return


def test_to_stored_serializes_trusted_proxies() -> None:
    """Trusted proxies are persisted with full CIDR notation as strings."""
    conf = {
        "server_port": 8123,
        "trusted_proxies": [ip_network("10.0.0.0/24"), ip_network("172.16.0.5/32")],
    }
    stored = to_stored(conf)
    assert stored["trusted_proxies"] == ["10.0.0.0/24", "172.16.0.5/32"]


def test_to_stored_drops_deprecated_base_url() -> None:
    """The deprecated base_url key is not persisted."""
    conf = {"server_port": 8123, "base_url": "https://old.example"}
    stored = to_stored(conf)
    assert "base_url" not in stored
    assert stored["server_port"] == 8123


async def test_first_boot_imports_yaml(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """A populated YAML block is imported into the store on first boot."""
    with patch("asyncio.BaseEventLoop.create_server", return_value=Mock()):
        assert await async_setup_component(
            hass,
            "http",
            {
                "http": {
                    "server_port": 8125,
                    "cors_allowed_origins": ["https://example.com"],
                }
            },
        )
        await hass.async_block_till_done()

    stored = hass_storage[USER_CONFIG_STORAGE_KEY]
    assert stored["version"] == USER_CONFIG_STORAGE_VERSION
    assert stored["data"]["server_port"] == 8125
    assert stored["data"]["cors_allowed_origins"] == ["https://example.com"]
    assert ("http", "deprecated_yaml") in issue_registry.issues


async def test_first_boot_without_yaml_writes_defaults(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """With no YAML block present, the store is initialized with defaults."""
    with patch("asyncio.BaseEventLoop.create_server", return_value=Mock()):
        assert await async_setup_component(hass, "http", {})
        await hass.async_block_till_done()

    stored = hass_storage[USER_CONFIG_STORAGE_KEY]
    assert stored["data"]["server_port"] == 8123
    assert ("http", "deprecated_yaml") not in issue_registry.issues


async def test_second_boot_prefers_stored_over_yaml(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """When stored config exists, YAML is ignored and the deprecation remains."""
    hass_storage[USER_CONFIG_STORAGE_KEY] = {
        "version": USER_CONFIG_STORAGE_VERSION,
        "minor_version": 1,
        "key": USER_CONFIG_STORAGE_KEY,
        "data": {
            "server_port": 9999,
            "cors_allowed_origins": ["https://stored.example"],
            "ssl_profile": "modern",
            "use_x_frame_options": True,
            "ip_ban_enabled": True,
            "login_attempts_threshold": -1,
        },
    }

    with (
        patch("asyncio.BaseEventLoop.create_server", return_value=Mock()) as srv,
        patch("homeassistant.components.http.is_hassio", return_value=False),
    ):
        assert await async_setup_component(
            hass, "http", {"http": {"server_port": 12345}}
        )
        await hass.async_start()
        await hass.async_block_till_done()

    # Stored port 9999 wins over YAML port 12345.
    srv.assert_called_once_with(
        ANY,
        ["0.0.0.0", "::"],
        9999,
        ssl=None,
        backlog=128,
        reuse_address=None,
        reuse_port=None,
    )
    assert ("http", "deprecated_yaml") in issue_registry.issues


async def test_trusted_proxies_round_trip_through_store(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """A CIDR network in YAML is preserved exactly when read back from storage."""
    with patch("asyncio.BaseEventLoop.create_server", return_value=Mock()):
        assert await async_setup_component(
            hass,
            "http",
            {
                "http": {
                    "use_x_forwarded_for": True,
                    "trusted_proxies": ["10.0.0.0/24"],
                }
            },
        )
        await hass.async_block_till_done()

    assert hass_storage[USER_CONFIG_STORAGE_KEY]["data"]["trusted_proxies"] == [
        "10.0.0.0/24"
    ]


async def test_invalid_stored_config_falls_back_to_defaults(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Stored config that no longer validates triggers a fallback and a repair."""
    hass_storage[USER_CONFIG_STORAGE_KEY] = {
        "version": USER_CONFIG_STORAGE_VERSION,
        "minor_version": 1,
        "key": USER_CONFIG_STORAGE_KEY,
        "data": {
            "server_port": 8123,
            "ssl_certificate": "/path/that/does/not/exist.pem",
            "cors_allowed_origins": ["https://cast.home-assistant.io"],
            "ssl_profile": "modern",
            "use_x_frame_options": True,
            "ip_ban_enabled": True,
            "login_attempts_threshold": -1,
        },
    }

    with patch("asyncio.BaseEventLoop.create_server", return_value=Mock()):
        assert await async_setup_component(hass, "http", {})
        await hass.async_block_till_done()

    assert ("http", "http_failed_to_start") in issue_registry.issues
