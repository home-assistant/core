"""Test the Matter integration init."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, call

from matter_server.client.exceptions import InvalidServerVersion
import pytest

from homeassistant.components.hassio import HassioAPIError
from homeassistant.components.matter.const import DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


async def test_raise_addon_task_in_progress(
    hass: HomeAssistant,
    addon_not_installed: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test raise ConfigEntryNotReady if an add-on task is in progress."""
    install_event = asyncio.Event()

    install_addon_original_side_effect = install_addon.side_effect

    async def install_addon_side_effect(hass: HomeAssistant, slug: str) -> None:
        """Mock install add-on."""
        await install_event.wait()
        await install_addon_original_side_effect(hass, slug)

    install_addon.side_effect = install_addon_side_effect

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": True,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await asyncio.sleep(0.05)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert install_addon.call_count == 1
    assert start_addon.call_count == 0

    # Check that we only call install add-on once if a task is in progress.
    await hass.config_entries.async_reload(entry.entry_id)
    await asyncio.sleep(0.05)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert install_addon.call_count == 1
    assert start_addon.call_count == 0

    install_event.set()
    await hass.async_block_till_done()

    assert install_addon.call_count == 1
    assert start_addon.call_count == 1


async def test_start_addon(
    hass: HomeAssistant,
    addon_installed: AsyncMock,
    addon_info: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test start the Matter Server add-on during entry setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": True,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert addon_info.call_count == 1
    assert install_addon.call_count == 0
    assert start_addon.call_count == 1
    assert start_addon.call_args == call(hass, "core_matter_server")


async def test_install_addon(
    hass: HomeAssistant,
    addon_not_installed: AsyncMock,
    addon_store_info: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test install and start the Matter add-on during entry setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": True,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert addon_store_info.call_count == 2
    assert install_addon.call_count == 1
    assert install_addon.call_args == call(hass, "core_matter_server")
    assert start_addon.call_count == 1
    assert start_addon.call_args == call(hass, "core_matter_server")


async def test_addon_info_failure(
    hass: HomeAssistant,
    addon_installed: AsyncMock,
    addon_info: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test failure to get add-on info for Matter add-on during entry setup."""
    addon_info.side_effect = HassioAPIError("Boom")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": True,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert addon_info.call_count == 1
    assert install_addon.call_count == 0
    assert start_addon.call_count == 0


@pytest.mark.parametrize(
    "addon_version, update_available, update_calls, backup_calls, "
    "update_addon_side_effect, create_backup_side_effect",
    [
        ("1.0.0", True, 1, 1, None, None),
        ("1.0.0", False, 0, 0, None, None),
        ("1.0.0", True, 1, 1, HassioAPIError("Boom"), None),
        ("1.0.0", True, 0, 1, None, HassioAPIError("Boom")),
    ],
)
async def test_update_addon(
    hass: HomeAssistant,
    addon_installed: AsyncMock,
    addon_running: AsyncMock,
    addon_info: AsyncMock,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
    create_backup: AsyncMock,
    update_addon: AsyncMock,
    matter_client: MagicMock,
    addon_version: str,
    update_available: bool,
    update_calls: int,
    backup_calls: int,
    update_addon_side_effect: Exception | None,
    create_backup_side_effect: Exception | None,
):
    """Test update the Matter add-on during entry setup."""
    addon_info.return_value["version"] = addon_version
    addon_info.return_value["update_available"] = update_available
    create_backup.side_effect = create_backup_side_effect
    update_addon.side_effect = update_addon_side_effect
    matter_client.connect.side_effect = InvalidServerVersion("Invalid version")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": True,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert create_backup.call_count == backup_calls
    assert update_addon.call_count == update_calls


async def test_issue_registry_invalid_version(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test issue registry for invalid version."""
    original_connect_side_effect = matter_client.connect.side_effect
    matter_client.connect.side_effect = InvalidServerVersion("Invalid version")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": False,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    issue_reg = ir.async_get(hass)
    entry_state = entry.state
    assert entry_state is ConfigEntryState.SETUP_RETRY
    assert issue_reg.async_get_issue(DOMAIN, "invalid_server_version")

    matter_client.connect.side_effect = original_connect_side_effect

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert not issue_reg.async_get_issue(DOMAIN, "invalid_server_version")


@pytest.mark.parametrize(
    "stop_addon_side_effect, entry_state",
    [
        (None, ConfigEntryState.NOT_LOADED),
        (HassioAPIError("Boom"), ConfigEntryState.LOADED),
    ],
)
async def test_stop_addon(
    hass,
    matter_client: MagicMock,
    addon_installed: AsyncMock,
    addon_running: AsyncMock,
    addon_info: AsyncMock,
    stop_addon: AsyncMock,
    stop_addon_side_effect: Exception | None,
    entry_state: ConfigEntryState,
):
    """Test stop the Matter add-on on entry unload if entry is disabled."""
    stop_addon.side_effect = stop_addon_side_effect
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={
            "url": "ws://host1:5581/ws",
            "use_addon": True,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert addon_info.call_count == 1
    addon_info.reset_mock()

    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert entry.state == entry_state
    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call(hass, "core_matter_server")


async def test_remove_entry(
    hass: HomeAssistant,
    addon_installed: AsyncMock,
    stop_addon: AsyncMock,
    create_backup: AsyncMock,
    uninstall_addon: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test remove the config entry."""
    # test successful remove without created add-on
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={"integration_created_addon": False},
    )
    entry.add_to_hass(hass)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    await hass.config_entries.async_remove(entry.entry_id)

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

    # test successful remove with created add-on
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Matter",
        data={"integration_created_addon": True},
    )
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call(hass, "core_matter_server")
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass,
        {"name": "addon_core_matter_server_1.0.0", "addons": ["core_matter_server"]},
        partial=True,
    )
    assert uninstall_addon.call_count == 1
    assert uninstall_addon.call_args == call(hass, "core_matter_server")
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    stop_addon.reset_mock()
    create_backup.reset_mock()
    uninstall_addon.reset_mock()

    # test add-on stop failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    stop_addon.side_effect = HassioAPIError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call(hass, "core_matter_server")
    assert create_backup.call_count == 0
    assert uninstall_addon.call_count == 0
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to stop the Matter Server add-on" in caplog.text
    stop_addon.side_effect = None
    stop_addon.reset_mock()
    create_backup.reset_mock()
    uninstall_addon.reset_mock()

    # test create backup failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    create_backup.side_effect = HassioAPIError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call(hass, "core_matter_server")
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass,
        {"name": "addon_core_matter_server_1.0.0", "addons": ["core_matter_server"]},
        partial=True,
    )
    assert uninstall_addon.call_count == 0
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to create a backup of the Matter Server add-on" in caplog.text
    create_backup.side_effect = None
    stop_addon.reset_mock()
    create_backup.reset_mock()
    uninstall_addon.reset_mock()

    # test add-on uninstall failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    uninstall_addon.side_effect = HassioAPIError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call(hass, "core_matter_server")
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass,
        {"name": "addon_core_matter_server_1.0.0", "addons": ["core_matter_server"]},
        partial=True,
    )
    assert uninstall_addon.call_count == 1
    assert uninstall_addon.call_args == call(hass, "core_matter_server")
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to uninstall the Matter Server add-on" in caplog.text
