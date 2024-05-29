"""Test the addon manager."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
import logging
from typing import Any
from unittest.mock import AsyncMock, call, patch

import pytest

from homeassistant.components.hassio.addon_manager import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
)
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.core import HomeAssistant

LOGGER = logging.getLogger(__name__)


@pytest.fixture(name="addon_manager")
def addon_manager_fixture(hass: HomeAssistant) -> AddonManager:
    """Return an AddonManager instance."""
    return AddonManager(hass, LOGGER, "Test", "test_addon")


@pytest.fixture(name="addon_not_installed")
def addon_not_installed_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on not installed."""
    addon_store_info.return_value["available"] = True
    return addon_info


@pytest.fixture(name="addon_installed")
def mock_addon_installed(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on already installed but not running."""
    addon_store_info.return_value = {
        "available": True,
        "installed": "1.0.0",
        "state": "stopped",
        "version": "1.0.0",
    }
    addon_info.return_value["available"] = True
    addon_info.return_value["hostname"] = "core-test-addon"
    addon_info.return_value["state"] = "stopped"
    addon_info.return_value["version"] = "1.0.0"
    return addon_info


@pytest.fixture(name="get_addon_discovery_info")
def get_addon_discovery_info_fixture() -> Generator[AsyncMock, None, None]:
    """Mock get add-on discovery info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_discovery_info"
    ) as get_addon_discovery_info:
        yield get_addon_discovery_info


@pytest.fixture(name="addon_store_info")
def addon_store_info_fixture() -> Generator[AsyncMock, None, None]:
    """Mock Supervisor add-on store info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_store_info"
    ) as addon_store_info:
        addon_store_info.return_value = {
            "available": False,
            "installed": None,
            "state": None,
            "version": "1.0.0",
        }
        yield addon_store_info


@pytest.fixture(name="addon_info")
def addon_info_fixture() -> Generator[AsyncMock, None, None]:
    """Mock Supervisor add-on info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_info",
    ) as addon_info:
        addon_info.return_value = {
            "available": False,
            "hostname": None,
            "options": {},
            "state": None,
            "update_available": False,
            "version": None,
        }
        yield addon_info


@pytest.fixture(name="set_addon_options")
def set_addon_options_fixture() -> Generator[AsyncMock, None, None]:
    """Mock set add-on options."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_set_addon_options"
    ) as set_options:
        yield set_options


@pytest.fixture(name="install_addon")
def install_addon_fixture() -> Generator[AsyncMock, None, None]:
    """Mock install add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_install_addon"
    ) as install_addon:
        yield install_addon


@pytest.fixture(name="uninstall_addon")
def uninstall_addon_fixture() -> Generator[AsyncMock, None, None]:
    """Mock uninstall add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_uninstall_addon"
    ) as uninstall_addon:
        yield uninstall_addon


@pytest.fixture(name="start_addon")
def start_addon_fixture() -> Generator[AsyncMock, None, None]:
    """Mock start add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_start_addon"
    ) as start_addon:
        yield start_addon


@pytest.fixture(name="restart_addon")
def restart_addon_fixture() -> Generator[AsyncMock, None, None]:
    """Mock restart add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_restart_addon"
    ) as restart_addon:
        yield restart_addon


@pytest.fixture(name="stop_addon")
def stop_addon_fixture() -> Generator[AsyncMock, None, None]:
    """Mock stop add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_stop_addon"
    ) as stop_addon:
        yield stop_addon


@pytest.fixture(name="create_backup")
def create_backup_fixture() -> Generator[AsyncMock, None, None]:
    """Mock create backup."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_create_backup"
    ) as create_backup:
        yield create_backup


@pytest.fixture(name="update_addon")
def mock_update_addon() -> Generator[AsyncMock, None, None]:
    """Mock update add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_update_addon"
    ) as update_addon:
        yield update_addon


async def test_not_installed_raises_exception(
    addon_manager: AddonManager,
    addon_not_installed: dict[str, Any],
) -> None:
    """Test addon not installed raises exception."""
    addon_config = {"test_key": "test"}

    with pytest.raises(AddonError) as err:
        await addon_manager.async_configure_addon(addon_config)

    assert str(err.value) == "Test add-on is not installed"

    with pytest.raises(AddonError) as err:
        await addon_manager.async_update_addon()

    assert str(err.value) == "Test add-on is not installed"


async def test_not_available_raises_exception(
    addon_manager: AddonManager,
    addon_store_info: AsyncMock,
    addon_info: AsyncMock,
) -> None:
    """Test addon not available raises exception."""
    addon_store_info.return_value["available"] = False
    addon_info.return_value["available"] = False

    with pytest.raises(AddonError) as err:
        await addon_manager.async_install_addon()

    assert str(err.value) == "Test add-on is not available anymore"

    with pytest.raises(AddonError) as err:
        await addon_manager.async_update_addon()

    assert str(err.value) == "Test add-on is not available anymore"


async def test_get_addon_discovery_info(
    addon_manager: AddonManager, get_addon_discovery_info: AsyncMock
) -> None:
    """Test get addon discovery info."""
    get_addon_discovery_info.return_value = {"config": {"test_key": "test"}}

    assert await addon_manager.async_get_addon_discovery_info() == {"test_key": "test"}

    assert get_addon_discovery_info.call_count == 1


async def test_missing_addon_discovery_info(
    addon_manager: AddonManager, get_addon_discovery_info: AsyncMock
) -> None:
    """Test missing addon discovery info."""
    get_addon_discovery_info.return_value = None

    with pytest.raises(AddonError):
        await addon_manager.async_get_addon_discovery_info()

    assert get_addon_discovery_info.call_count == 1


async def test_get_addon_discovery_info_error(
    addon_manager: AddonManager, get_addon_discovery_info: AsyncMock
) -> None:
    """Test get addon discovery info raises error."""
    get_addon_discovery_info.side_effect = HassioAPIError("Boom")

    with pytest.raises(AddonError) as err:
        assert await addon_manager.async_get_addon_discovery_info()

    assert str(err.value) == "Failed to get the Test add-on discovery info: Boom"

    assert get_addon_discovery_info.call_count == 1


async def test_get_addon_info_not_installed(
    addon_manager: AddonManager, addon_not_installed: AsyncMock
) -> None:
    """Test get addon info when addon is not installed.."""
    assert await addon_manager.async_get_addon_info() == AddonInfo(
        available=True,
        hostname=None,
        options={},
        state=AddonState.NOT_INSTALLED,
        update_available=False,
        version=None,
    )


@pytest.mark.parametrize(
    ("addon_info_state", "addon_state"),
    [("started", AddonState.RUNNING), ("stopped", AddonState.NOT_RUNNING)],
)
async def test_get_addon_info(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    addon_info_state: str,
    addon_state: AddonState,
) -> None:
    """Test get addon info when addon is installed."""
    addon_installed.return_value["state"] = addon_info_state
    assert await addon_manager.async_get_addon_info() == AddonInfo(
        available=True,
        hostname="core-test-addon",
        options={},
        state=addon_state,
        update_available=False,
        version="1.0.0",
    )


@pytest.mark.parametrize(
    (
        "addon_info_error",
        "addon_info_calls",
        "addon_store_info_error",
        "addon_store_info_calls",
    ),
    [(HassioAPIError("Boom"), 1, None, 1), (None, 0, HassioAPIError("Boom"), 1)],
)
async def test_get_addon_info_error(
    addon_manager: AddonManager,
    addon_info: AsyncMock,
    addon_store_info: AsyncMock,
    addon_installed: AsyncMock,
    addon_info_error: Exception | None,
    addon_info_calls: int,
    addon_store_info_error: Exception | None,
    addon_store_info_calls: int,
) -> None:
    """Test get addon info raises error."""
    addon_info.side_effect = addon_info_error
    addon_store_info.side_effect = addon_store_info_error

    with pytest.raises(AddonError) as err:
        await addon_manager.async_get_addon_info()

    assert str(err.value) == "Failed to get the Test add-on info: Boom"

    assert addon_info.call_count == addon_info_calls
    assert addon_store_info.call_count == addon_store_info_calls


async def test_set_addon_options(
    hass: HomeAssistant, addon_manager: AddonManager, set_addon_options: AsyncMock
) -> None:
    """Test set addon options."""
    await addon_manager.async_set_addon_options({"test_key": "test"})

    assert set_addon_options.call_count == 1
    assert set_addon_options.call_args == call(
        hass, "test_addon", {"options": {"test_key": "test"}}
    )


async def test_set_addon_options_error(
    hass: HomeAssistant, addon_manager: AddonManager, set_addon_options: AsyncMock
) -> None:
    """Test set addon options raises error."""
    set_addon_options.side_effect = HassioAPIError("Boom")

    with pytest.raises(AddonError) as err:
        await addon_manager.async_set_addon_options({"test_key": "test"})

    assert str(err.value) == "Failed to set the Test add-on options: Boom"

    assert set_addon_options.call_count == 1
    assert set_addon_options.call_args == call(
        hass, "test_addon", {"options": {"test_key": "test"}}
    )


async def test_install_addon(
    addon_manager: AddonManager,
    install_addon: AsyncMock,
    addon_store_info: AsyncMock,
    addon_info: AsyncMock,
) -> None:
    """Test install addon."""
    addon_store_info.return_value["available"] = True
    addon_info.return_value["available"] = True

    await addon_manager.async_install_addon()

    assert install_addon.call_count == 1


async def test_install_addon_error(
    addon_manager: AddonManager,
    install_addon: AsyncMock,
    addon_store_info: AsyncMock,
    addon_info: AsyncMock,
) -> None:
    """Test install addon raises error."""
    addon_store_info.return_value["available"] = True
    addon_info.return_value["available"] = True
    install_addon.side_effect = HassioAPIError("Boom")

    with pytest.raises(AddonError) as err:
        await addon_manager.async_install_addon()

    assert str(err.value) == "Failed to install the Test add-on: Boom"

    assert install_addon.call_count == 1


async def test_schedule_install_addon(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    install_addon: AsyncMock,
) -> None:
    """Test schedule install addon."""
    install_task = addon_manager.async_schedule_install_addon()

    assert addon_manager.task_in_progress() is True

    assert await addon_manager.async_get_addon_info() == AddonInfo(
        available=True,
        hostname="core-test-addon",
        options={},
        state=AddonState.INSTALLING,
        update_available=False,
        version="1.0.0",
    )

    # Make sure that actually only one install task is running.
    install_task_two = addon_manager.async_schedule_install_addon()

    await asyncio.gather(install_task, install_task_two)

    assert addon_manager.task_in_progress() is False
    assert install_addon.call_count == 1

    install_addon.reset_mock()

    # Test that another call can be made after the install is done.
    await addon_manager.async_schedule_install_addon()

    assert install_addon.call_count == 1


async def test_schedule_install_addon_error(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    install_addon: AsyncMock,
) -> None:
    """Test schedule install addon raises error."""
    install_addon.side_effect = HassioAPIError("Boom")

    with pytest.raises(AddonError) as err:
        await addon_manager.async_schedule_install_addon()

    assert str(err.value) == "Failed to install the Test add-on: Boom"

    assert install_addon.call_count == 1


async def test_schedule_install_addon_logs_error(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    install_addon: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test schedule install addon logs error."""
    install_addon.side_effect = HassioAPIError("Boom")

    await addon_manager.async_schedule_install_addon(catch_error=True)

    assert "Failed to install the Test add-on: Boom" in caplog.text
    assert install_addon.call_count == 1


async def test_uninstall_addon(
    addon_manager: AddonManager, uninstall_addon: AsyncMock
) -> None:
    """Test uninstall addon."""
    await addon_manager.async_uninstall_addon()

    assert uninstall_addon.call_count == 1


async def test_uninstall_addon_error(
    addon_manager: AddonManager, uninstall_addon: AsyncMock
) -> None:
    """Test uninstall addon raises error."""
    uninstall_addon.side_effect = HassioAPIError("Boom")

    with pytest.raises(AddonError) as err:
        await addon_manager.async_uninstall_addon()

    assert str(err.value) == "Failed to uninstall the Test add-on: Boom"

    assert uninstall_addon.call_count == 1


async def test_start_addon(addon_manager: AddonManager, start_addon: AsyncMock) -> None:
    """Test start addon."""
    await addon_manager.async_start_addon()

    assert start_addon.call_count == 1


async def test_start_addon_error(
    addon_manager: AddonManager, start_addon: AsyncMock
) -> None:
    """Test start addon raises error."""
    start_addon.side_effect = HassioAPIError("Boom")

    with pytest.raises(AddonError) as err:
        await addon_manager.async_start_addon()

    assert str(err.value) == "Failed to start the Test add-on: Boom"

    assert start_addon.call_count == 1


async def test_schedule_start_addon(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test schedule start addon."""
    start_task = addon_manager.async_schedule_start_addon()

    assert addon_manager.task_in_progress() is True

    # Make sure that actually only one start task is running.
    start_task_two = addon_manager.async_schedule_start_addon()

    await asyncio.gather(start_task, start_task_two)

    assert addon_manager.task_in_progress() is False
    assert start_addon.call_count == 1

    start_addon.reset_mock()

    # Test that another call can be made after the start is done.
    await addon_manager.async_schedule_start_addon()

    assert start_addon.call_count == 1


async def test_schedule_start_addon_error(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test schedule start addon raises error."""
    start_addon.side_effect = HassioAPIError("Boom")

    with pytest.raises(AddonError) as err:
        await addon_manager.async_schedule_start_addon()

    assert str(err.value) == "Failed to start the Test add-on: Boom"

    assert start_addon.call_count == 1


async def test_schedule_start_addon_logs_error(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    start_addon: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test schedule start addon logs error."""
    start_addon.side_effect = HassioAPIError("Boom")

    await addon_manager.async_schedule_start_addon(catch_error=True)

    assert "Failed to start the Test add-on: Boom" in caplog.text
    assert start_addon.call_count == 1


async def test_restart_addon(
    addon_manager: AddonManager, restart_addon: AsyncMock
) -> None:
    """Test restart addon."""
    await addon_manager.async_restart_addon()

    assert restart_addon.call_count == 1


async def test_restart_addon_error(
    addon_manager: AddonManager, restart_addon: AsyncMock
) -> None:
    """Test restart addon raises error."""
    restart_addon.side_effect = HassioAPIError("Boom")

    with pytest.raises(AddonError) as err:
        await addon_manager.async_restart_addon()

    assert str(err.value) == "Failed to restart the Test add-on: Boom"

    assert restart_addon.call_count == 1


async def test_schedule_restart_addon(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    restart_addon: AsyncMock,
) -> None:
    """Test schedule restart addon."""
    restart_task = addon_manager.async_schedule_restart_addon()

    assert addon_manager.task_in_progress() is True

    # Make sure that actually only one start task is running.
    restart_task_two = addon_manager.async_schedule_restart_addon()

    await asyncio.gather(restart_task, restart_task_two)

    assert addon_manager.task_in_progress() is False
    assert restart_addon.call_count == 1

    restart_addon.reset_mock()

    # Test that another call can be made after the restart is done.
    await addon_manager.async_schedule_restart_addon()

    assert restart_addon.call_count == 1


async def test_schedule_restart_addon_error(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    restart_addon: AsyncMock,
) -> None:
    """Test schedule restart addon raises error."""
    restart_addon.side_effect = HassioAPIError("Boom")

    with pytest.raises(AddonError) as err:
        await addon_manager.async_schedule_restart_addon()

    assert str(err.value) == "Failed to restart the Test add-on: Boom"

    assert restart_addon.call_count == 1


async def test_schedule_restart_addon_logs_error(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    restart_addon: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test schedule restart addon logs error."""
    restart_addon.side_effect = HassioAPIError("Boom")

    await addon_manager.async_schedule_restart_addon(catch_error=True)

    assert "Failed to restart the Test add-on: Boom" in caplog.text
    assert restart_addon.call_count == 1


async def test_stop_addon(addon_manager: AddonManager, stop_addon: AsyncMock) -> None:
    """Test stop addon."""
    await addon_manager.async_stop_addon()

    assert stop_addon.call_count == 1


async def test_stop_addon_error(
    addon_manager: AddonManager, stop_addon: AsyncMock
) -> None:
    """Test stop addon raises error."""
    stop_addon.side_effect = HassioAPIError("Boom")

    with pytest.raises(AddonError) as err:
        await addon_manager.async_stop_addon()

    assert str(err.value) == "Failed to stop the Test add-on: Boom"

    assert stop_addon.call_count == 1


async def test_update_addon(
    hass: HomeAssistant,
    addon_manager: AddonManager,
    addon_info: AsyncMock,
    addon_installed: AsyncMock,
    create_backup: AsyncMock,
    update_addon: AsyncMock,
) -> None:
    """Test update addon."""
    addon_info.return_value["update_available"] = True

    await addon_manager.async_update_addon()

    assert addon_info.call_count == 2
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass, {"name": "addon_test_addon_1.0.0", "addons": ["test_addon"]}, partial=True
    )
    assert update_addon.call_count == 1


async def test_update_addon_no_update(
    addon_manager: AddonManager,
    addon_info: AsyncMock,
    addon_installed: AsyncMock,
    create_backup: AsyncMock,
    update_addon: AsyncMock,
) -> None:
    """Test update addon without update available."""
    addon_info.return_value["update_available"] = False

    await addon_manager.async_update_addon()

    assert addon_info.call_count == 1
    assert create_backup.call_count == 0
    assert update_addon.call_count == 0


async def test_update_addon_error(
    hass: HomeAssistant,
    addon_manager: AddonManager,
    addon_info: AsyncMock,
    addon_installed: AsyncMock,
    create_backup: AsyncMock,
    update_addon: AsyncMock,
) -> None:
    """Test update addon raises error."""
    addon_info.return_value["update_available"] = True
    update_addon.side_effect = HassioAPIError("Boom")

    with pytest.raises(AddonError) as err:
        await addon_manager.async_update_addon()

    assert str(err.value) == "Failed to update the Test add-on: Boom"

    assert addon_info.call_count == 2
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass, {"name": "addon_test_addon_1.0.0", "addons": ["test_addon"]}, partial=True
    )
    assert update_addon.call_count == 1


async def test_schedule_update_addon(
    hass: HomeAssistant,
    addon_manager: AddonManager,
    addon_info: AsyncMock,
    addon_installed: AsyncMock,
    create_backup: AsyncMock,
    update_addon: AsyncMock,
) -> None:
    """Test schedule update addon."""
    addon_info.return_value["update_available"] = True

    update_task = addon_manager.async_schedule_update_addon()

    assert addon_manager.task_in_progress() is True

    assert await addon_manager.async_get_addon_info() == AddonInfo(
        available=True,
        hostname="core-test-addon",
        options={},
        state=AddonState.UPDATING,
        update_available=True,
        version="1.0.0",
    )

    # Make sure that actually only one update task is running.
    update_task_two = addon_manager.async_schedule_update_addon()

    await asyncio.gather(update_task, update_task_two)

    assert addon_manager.task_in_progress() is False
    assert addon_info.call_count == 3
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass, {"name": "addon_test_addon_1.0.0", "addons": ["test_addon"]}, partial=True
    )
    assert update_addon.call_count == 1

    update_addon.reset_mock()

    # Test that another call can be made after the update is done.
    await addon_manager.async_schedule_update_addon()

    assert update_addon.call_count == 1


@pytest.mark.parametrize(
    (
        "create_backup_error",
        "create_backup_calls",
        "update_addon_error",
        "update_addon_calls",
        "error_message",
    ),
    [
        (
            HassioAPIError("Boom"),
            1,
            None,
            0,
            "Failed to create a backup of the Test add-on: Boom",
        ),
        (
            None,
            1,
            HassioAPIError("Boom"),
            1,
            "Failed to update the Test add-on: Boom",
        ),
    ],
)
async def test_schedule_update_addon_error(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    create_backup: AsyncMock,
    update_addon: AsyncMock,
    create_backup_error: Exception | None,
    create_backup_calls: int,
    update_addon_error: Exception | None,
    update_addon_calls: int,
    error_message: str,
) -> None:
    """Test schedule update addon raises error."""
    addon_installed.return_value["update_available"] = True
    create_backup.side_effect = create_backup_error
    update_addon.side_effect = update_addon_error

    with pytest.raises(AddonError) as err:
        await addon_manager.async_schedule_update_addon()

    assert str(err.value) == error_message

    assert create_backup.call_count == create_backup_calls
    assert update_addon.call_count == update_addon_calls


@pytest.mark.parametrize(
    (
        "create_backup_error",
        "create_backup_calls",
        "update_addon_error",
        "update_addon_calls",
        "error_log",
    ),
    [
        (
            HassioAPIError("Boom"),
            1,
            None,
            0,
            "Failed to create a backup of the Test add-on: Boom",
        ),
        (
            None,
            1,
            HassioAPIError("Boom"),
            1,
            "Failed to update the Test add-on: Boom",
        ),
    ],
)
async def test_schedule_update_addon_logs_error(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    create_backup: AsyncMock,
    update_addon: AsyncMock,
    create_backup_error: Exception | None,
    create_backup_calls: int,
    update_addon_error: Exception | None,
    update_addon_calls: int,
    error_log: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test schedule update addon logs error."""
    addon_installed.return_value["update_available"] = True
    create_backup.side_effect = create_backup_error
    update_addon.side_effect = update_addon_error

    await addon_manager.async_schedule_update_addon(catch_error=True)

    assert error_log in caplog.text
    assert create_backup.call_count == create_backup_calls
    assert update_addon.call_count == update_addon_calls


async def test_create_backup(
    hass: HomeAssistant,
    addon_manager: AddonManager,
    addon_info: AsyncMock,
    addon_installed: AsyncMock,
    create_backup: AsyncMock,
) -> None:
    """Test creating a backup of the addon."""
    await addon_manager.async_create_backup()

    assert addon_info.call_count == 1
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass, {"name": "addon_test_addon_1.0.0", "addons": ["test_addon"]}, partial=True
    )


async def test_create_backup_error(
    hass: HomeAssistant,
    addon_manager: AddonManager,
    addon_info: AsyncMock,
    addon_installed: AsyncMock,
    create_backup: AsyncMock,
) -> None:
    """Test creating a backup of the addon raises error."""
    create_backup.side_effect = HassioAPIError("Boom")

    with pytest.raises(AddonError) as err:
        await addon_manager.async_create_backup()

    assert str(err.value) == "Failed to create a backup of the Test add-on: Boom"

    assert addon_info.call_count == 1
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass, {"name": "addon_test_addon_1.0.0", "addons": ["test_addon"]}, partial=True
    )


async def test_schedule_install_setup_addon(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    install_addon: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test schedule install setup addon."""
    install_task = addon_manager.async_schedule_install_setup_addon(
        {"test_key": "test"}
    )

    assert addon_manager.task_in_progress() is True

    # Make sure that actually only one install task is running.
    install_task_two = addon_manager.async_schedule_install_setup_addon(
        {"test_key": "test"}
    )

    await asyncio.gather(install_task, install_task_two)

    assert addon_manager.task_in_progress() is False
    assert install_addon.call_count == 1
    assert set_addon_options.call_count == 1
    assert start_addon.call_count == 1

    install_addon.reset_mock()
    set_addon_options.reset_mock()
    start_addon.reset_mock()

    # Test that another call can be made after the install is done.
    await addon_manager.async_schedule_install_setup_addon({"test_key": "test"})

    assert install_addon.call_count == 1
    assert set_addon_options.call_count == 1
    assert start_addon.call_count == 1


@pytest.mark.parametrize(
    (
        "install_addon_error",
        "install_addon_calls",
        "set_addon_options_error",
        "set_addon_options_calls",
        "start_addon_error",
        "start_addon_calls",
        "error_message",
    ),
    [
        (
            HassioAPIError("Boom"),
            1,
            None,
            0,
            None,
            0,
            "Failed to install the Test add-on: Boom",
        ),
        (
            None,
            1,
            HassioAPIError("Boom"),
            1,
            None,
            0,
            "Failed to set the Test add-on options: Boom",
        ),
        (
            None,
            1,
            None,
            1,
            HassioAPIError("Boom"),
            1,
            "Failed to start the Test add-on: Boom",
        ),
    ],
)
async def test_schedule_install_setup_addon_error(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    install_addon: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
    install_addon_error: Exception | None,
    install_addon_calls: int,
    set_addon_options_error: Exception | None,
    set_addon_options_calls: int,
    start_addon_error: Exception | None,
    start_addon_calls: int,
    error_message: str,
) -> None:
    """Test schedule install setup addon raises error."""
    install_addon.side_effect = install_addon_error
    set_addon_options.side_effect = set_addon_options_error
    start_addon.side_effect = start_addon_error

    with pytest.raises(AddonError) as err:
        await addon_manager.async_schedule_install_setup_addon({"test_key": "test"})

    assert str(err.value) == error_message

    assert install_addon.call_count == install_addon_calls
    assert set_addon_options.call_count == set_addon_options_calls
    assert start_addon.call_count == start_addon_calls


@pytest.mark.parametrize(
    (
        "install_addon_error",
        "install_addon_calls",
        "set_addon_options_error",
        "set_addon_options_calls",
        "start_addon_error",
        "start_addon_calls",
        "error_log",
    ),
    [
        (
            HassioAPIError("Boom"),
            1,
            None,
            0,
            None,
            0,
            "Failed to install the Test add-on: Boom",
        ),
        (
            None,
            1,
            HassioAPIError("Boom"),
            1,
            None,
            0,
            "Failed to set the Test add-on options: Boom",
        ),
        (
            None,
            1,
            None,
            1,
            HassioAPIError("Boom"),
            1,
            "Failed to start the Test add-on: Boom",
        ),
    ],
)
async def test_schedule_install_setup_addon_logs_error(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    install_addon: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
    install_addon_error: Exception | None,
    install_addon_calls: int,
    set_addon_options_error: Exception | None,
    set_addon_options_calls: int,
    start_addon_error: Exception | None,
    start_addon_calls: int,
    error_log: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test schedule install setup addon logs error."""
    install_addon.side_effect = install_addon_error
    set_addon_options.side_effect = set_addon_options_error
    start_addon.side_effect = start_addon_error

    await addon_manager.async_schedule_install_setup_addon(
        {"test_key": "test"}, catch_error=True
    )

    assert error_log in caplog.text
    assert install_addon.call_count == install_addon_calls
    assert set_addon_options.call_count == set_addon_options_calls
    assert start_addon.call_count == start_addon_calls


async def test_schedule_setup_addon(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test schedule setup addon."""
    start_task = addon_manager.async_schedule_setup_addon({"test_key": "test"})

    assert addon_manager.task_in_progress() is True

    # Make sure that actually only one start task is running.
    start_task_two = addon_manager.async_schedule_setup_addon({"test_key": "test"})

    await asyncio.gather(start_task, start_task_two)

    assert addon_manager.task_in_progress() is False
    assert set_addon_options.call_count == 1
    assert start_addon.call_count == 1

    set_addon_options.reset_mock()
    start_addon.reset_mock()

    # Test that another call can be made after the start is done.
    await addon_manager.async_schedule_setup_addon({"test_key": "test"})

    assert set_addon_options.call_count == 1
    assert start_addon.call_count == 1


@pytest.mark.parametrize(
    (
        "set_addon_options_error",
        "set_addon_options_calls",
        "start_addon_error",
        "start_addon_calls",
        "error_message",
    ),
    [
        (
            HassioAPIError("Boom"),
            1,
            None,
            0,
            "Failed to set the Test add-on options: Boom",
        ),
        (
            None,
            1,
            HassioAPIError("Boom"),
            1,
            "Failed to start the Test add-on: Boom",
        ),
    ],
)
async def test_schedule_setup_addon_error(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
    set_addon_options_error: Exception | None,
    set_addon_options_calls: int,
    start_addon_error: Exception | None,
    start_addon_calls: int,
    error_message: str,
) -> None:
    """Test schedule setup addon raises error."""
    set_addon_options.side_effect = set_addon_options_error
    start_addon.side_effect = start_addon_error

    with pytest.raises(AddonError) as err:
        await addon_manager.async_schedule_setup_addon({"test_key": "test"})

    assert str(err.value) == error_message

    assert set_addon_options.call_count == set_addon_options_calls
    assert start_addon.call_count == start_addon_calls


@pytest.mark.parametrize(
    (
        "set_addon_options_error",
        "set_addon_options_calls",
        "start_addon_error",
        "start_addon_calls",
        "error_log",
    ),
    [
        (
            HassioAPIError("Boom"),
            1,
            None,
            0,
            "Failed to set the Test add-on options: Boom",
        ),
        (
            None,
            1,
            HassioAPIError("Boom"),
            1,
            "Failed to start the Test add-on: Boom",
        ),
    ],
)
async def test_schedule_setup_addon_logs_error(
    addon_manager: AddonManager,
    addon_installed: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
    set_addon_options_error: Exception | None,
    set_addon_options_calls: int,
    start_addon_error: Exception | None,
    start_addon_calls: int,
    error_log: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test schedule setup addon logs error."""
    set_addon_options.side_effect = set_addon_options_error
    start_addon.side_effect = start_addon_error

    await addon_manager.async_schedule_setup_addon(
        {"test_key": "test"}, catch_error=True
    )

    assert error_log in caplog.text
    assert set_addon_options.call_count == set_addon_options_calls
    assert start_addon.call_count == start_addon_calls
