"""Test fixtures for the Home Assistant Sky Connect integration."""
from unittest.mock import patch

import pytest


@pytest.fixture(name="addon_running")
def mock_addon_running(addon_store_info, addon_info):
    """Mock add-on already running."""
    addon_store_info.return_value = {
        "installed": "1.0.0",
        "state": "started",
        "version": "1.0.0",
    }
    addon_info.return_value["hostname"] = "core-silabs-multiprotocol"
    addon_info.return_value["state"] = "started"
    addon_info.return_value["version"] = "1.0.0"
    return addon_info


@pytest.fixture(name="addon_installed")
def mock_addon_installed(addon_store_info, addon_info):
    """Mock add-on already installed but not running."""
    addon_store_info.return_value = {
        "installed": "1.0.0",
        "state": "stopped",
        "version": "1.0.0",
    }
    addon_info.return_value["hostname"] = "core-silabs-multiprotocol"
    addon_info.return_value["state"] = "stopped"
    addon_info.return_value["version"] = "1.0.0"
    return addon_info


@pytest.fixture(name="addon_store_info")
def addon_store_info_fixture():
    """Mock Supervisor add-on store info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_store_info"
    ) as addon_store_info:
        addon_store_info.return_value = {
            "available": True,
            "installed": None,
            "state": None,
            "version": "1.0.0",
        }
        yield addon_store_info


@pytest.fixture(name="addon_info")
def addon_info_fixture():
    """Mock Supervisor add-on info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_info",
    ) as addon_info:
        addon_info.return_value = {
            "available": True,
            "hostname": None,
            "options": {},
            "state": None,
            "update_available": False,
            "version": None,
        }
        yield addon_info
