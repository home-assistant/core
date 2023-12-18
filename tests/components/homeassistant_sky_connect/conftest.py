"""Test fixtures for the Home Assistant SkyConnect integration."""
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(name="mock_usb_serial_by_id", autouse=True)
def mock_usb_serial_by_id_fixture() -> Generator[MagicMock, None, None]:
    """Mock usb serial by id."""
    with patch(
        "homeassistant.components.zha.config_flow.usb.get_serial_by_id"
    ) as mock_usb_serial_by_id:
        mock_usb_serial_by_id.side_effect = lambda x: x
        yield mock_usb_serial_by_id


@pytest.fixture(autouse=True)
def mock_zha():
    """Mock the zha integration."""
    mock_connect_app = MagicMock()
    mock_connect_app.__aenter__.return_value.backups.backups = [MagicMock()]
    mock_connect_app.__aenter__.return_value.backups.create_backup.return_value = (
        MagicMock()
    )

    with patch(
        "homeassistant.components.zha.radio_manager.ZhaRadioManager.connect_zigpy_app",
        return_value=mock_connect_app,
    ), patch(
        "homeassistant.components.zha.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(autouse=True)
def mock_zha_get_last_network_settings() -> Generator[None, None, None]:
    """Mock zha.api.async_get_last_network_settings."""

    with patch(
        "homeassistant.components.zha.api.async_get_last_network_settings",
        AsyncMock(return_value=None),
    ):
        yield


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


@pytest.fixture(name="set_addon_options")
def set_addon_options_fixture():
    """Mock set add-on options."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_set_addon_options"
    ) as set_options:
        yield set_options


@pytest.fixture(name="install_addon_side_effect")
def install_addon_side_effect_fixture(addon_store_info, addon_info):
    """Return the install add-on side effect."""

    async def install_addon(hass, slug):
        """Mock install add-on."""
        addon_store_info.return_value = {
            "installed": "1.0.0",
            "state": "stopped",
            "version": "1.0.0",
        }
        addon_info.return_value["hostname"] = "core-silabs-multiprotocol"
        addon_info.return_value["state"] = "stopped"
        addon_info.return_value["version"] = "1.0.0"

    return install_addon


@pytest.fixture(name="install_addon")
def mock_install_addon(install_addon_side_effect):
    """Mock install add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_install_addon",
        side_effect=install_addon_side_effect,
    ) as install_addon:
        yield install_addon


@pytest.fixture(name="start_addon")
def start_addon_fixture():
    """Mock start add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_start_addon"
    ) as start_addon:
        yield start_addon


@pytest.fixture(name="stop_addon")
def stop_addon_fixture():
    """Mock stop add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_stop_addon"
    ) as stop_addon:
        yield stop_addon


@pytest.fixture(name="uninstall_addon")
def uninstall_addon_fixture():
    """Mock uninstall add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_uninstall_addon"
    ) as uninstall_addon:
        yield uninstall_addon
