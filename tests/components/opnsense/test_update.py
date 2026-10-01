"""Tests for OPNsense firmware updates."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aiopnsense import OPNsenseConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator


@pytest.mark.parametrize(
    ("latest", "expected_state"),
    [("25.7.8", "off"), ("25.7.9", "on")],
)
async def test_firmware_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    latest: str,
    expected_state: str,
) -> None:
    """Test the firmware update entity reports available updates."""
    mock_opnsense_client.get_firmware_update_info.return_value["product"][
        "product_latest"
    ] = latest

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert state.state == expected_state
    assert state.attributes["installed_version"] == "25.7.8"
    assert state.attributes["latest_version"] == latest
    mock_opnsense_client.get_firmware_update_info.assert_awaited_once()


@pytest.mark.parametrize(
    ("status", "expected_latest"),
    [
        pytest.param("upgrade", "26.1", id="major-upgrade"),
        pytest.param(
            "update", "25.7.8 (package updates available)", id="package-updates"
        ),
    ],
)
async def test_firmware_update_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    status: str,
    expected_latest: str,
) -> None:
    """Test major and package-only updates reported by OPNsense."""
    mock_opnsense_client.get_firmware_update_info.return_value.update(
        {"status": status, "upgrade_major_version": "26.1"}
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["installed_version"] == "25.7.8"
    assert state.attributes["latest_version"] == expected_latest


async def test_firmware_release_notes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Show the pending package changes in firmware release notes."""
    mock_opnsense_client.get_firmware_update_info.return_value.update(
        {
            "status": "update",
            "status_msg": "There are 15 updates available, total download size is 36.0MiB.",
            "upgrade_packages": [
                {
                    "name": "opnsense",
                    "current_version": "25.7.8",
                    "new_version": "25.7.9",
                },
                {
                    "name": "suricata",
                    "current_version": "8.0.7",
                    "new_version": "8.0.7_1",
                },
            ],
            "downgrade_packages": [
                {"name": "example", "current_version": "2.0", "new_version": "1.9"}
            ],
            "new_packages": [{"name": "new-tool", "version": "1.0"}],
            "remove_packages": [{"name": "old-tool", "version": "0.9"}],
            "reinstall_packages": [{"name": "net-snmp", "version": "5.9.5.2,1"}],
        }
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.mock_title_firmware",
        }
    )
    result = await ws_client.receive_json()
    assert result["result"] == (
        "There are 15 updates available, total download size is 36.0MiB.\n\n"
        "### Upgrades\n"
        "- opnsense: 25.7.8 -> 25.7.9\n"
        "- suricata: 8.0.7 -> 8.0.7_1\n\n"
        "### Downgrades\n"
        "- example: 2.0 -> 1.9\n\n"
        "### New packages\n"
        "- new-tool: 1.0\n\n"
        "### Removed packages\n"
        "- old-tool: 0.9\n\n"
        "### Reinstalls\n"
        "- net-snmp: 5.9.5.2,1"
    )


async def test_firmware_release_notes_without_packages(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Return no release notes when there are no pending package changes."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.mock_title_firmware",
        }
    )
    assert (await ws_client.receive_json())["result"] is None


@pytest.mark.parametrize(
    ("status_reboot", "expected_summary"),
    [
        pytest.param("0", "There are 15 updates available.", id="no-reboot"),
        pytest.param(
            "1", "Reboot required. There are 15 updates available.", id="reboot"
        ),
    ],
)
async def test_firmware_update_details(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
    status_reboot: str,
    expected_summary: str,
) -> None:
    """Show OPNsense update status, reboot requirement, and changelog link."""
    mock_opnsense_client.get_firmware_update_info.return_value.update(
        {
            "status_msg": "There are 15 updates available.",
            "status_reboot": status_reboot,
        }
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert state.attributes["release_summary"] == expected_summary
    assert state.attributes["release_url"] == (
        "http://router.lan/ui/core/firmware#changelog"
    )
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.mock_title_firmware",
        }
    )
    assert (await ws_client.receive_json())["result"] == expected_summary


@pytest.mark.parametrize("status", ["update", "upgrade"])
async def test_firmware_install(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    status: str,
) -> None:
    """Test starting a current-series or major firmware upgrade."""
    mock_opnsense_client.get_firmware_update_info.return_value.update(
        {"status": status, "upgrade_major_version": "26.1"}
    )
    mock_opnsense_client.upgrade_firmware.return_value = {"status": "ok"}
    mock_opnsense_client.upgrade_status.return_value = {"status": "running"}
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": "update.mock_title_firmware"},
        blocking=True,
    )

    mock_opnsense_client.upgrade_firmware.assert_awaited_once_with(type=status)
    assert hass.states.get("update.mock_title_firmware").attributes["in_progress"]

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_opnsense_client.upgrade_status.assert_awaited_once()
    assert hass.states.get("update.mock_title_firmware").attributes["in_progress"]


@pytest.mark.parametrize("terminal_status", ["done", "reboot", "error"])
async def test_firmware_upgrade_finishes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    terminal_status: str,
) -> None:
    """Test terminal firmware status stops progress polling."""
    mock_opnsense_client.get_firmware_update_info.return_value["status"] = "update"
    mock_opnsense_client.upgrade_firmware.return_value = {"status": "ok"}
    mock_opnsense_client.upgrade_status.return_value = {"status": terminal_status}
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "update", "install", {"entity_id": "update.mock_title_firmware"}, blocking=True
    )
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not hass.states.get("update.mock_title_firmware").attributes["in_progress"]
    mock_opnsense_client.upgrade_status.assert_awaited_once()

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_opnsense_client.upgrade_status.assert_awaited_once()


async def test_firmware_upgrade_times_out(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test stalled firmware status eventually clears progress."""
    mock_opnsense_client.get_firmware_update_info.return_value["status"] = "update"
    mock_opnsense_client.upgrade_firmware.return_value = {"status": "ok"}
    mock_opnsense_client.upgrade_status.return_value = {"status": "running"}
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "update", "install", {"entity_id": "update.mock_title_firmware"}, blocking=True
    )
    freezer.tick(timedelta(hours=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not hass.states.get("update.mock_title_firmware").attributes["in_progress"]


async def test_firmware_upgrade_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test polling is cancelled when the update entity unloads."""
    mock_opnsense_client.get_firmware_update_info.return_value["status"] = "update"
    mock_opnsense_client.upgrade_firmware.return_value = {"status": "ok"}
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "update", "install", {"entity_id": "update.mock_title_firmware"}, blocking=True
    )
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_opnsense_client.upgrade_status.assert_not_awaited()


@pytest.mark.parametrize("response", [{"status": "failure"}, None])
async def test_firmware_install_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    response: dict[str, str] | None,
) -> None:
    """Test failed firmware start is reported to the caller."""
    mock_opnsense_client.get_firmware_update_info.return_value["status"] = "update"
    mock_opnsense_client.upgrade_firmware.return_value = response
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.mock_title_firmware"},
            blocking=True,
        )


async def test_firmware_install_without_update_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
) -> None:
    """Test ambiguous firmware status cannot start an upgrade."""
    mock_opnsense_client.get_firmware_update_info.return_value["product"][
        "product_latest"
    ] = "25.7.9"
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.mock_title_firmware"},
            blocking=True,
        )

    mock_opnsense_client.upgrade_firmware.assert_not_awaited()


async def test_firmware_update_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test missing data and communication failures make the entity unavailable."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_opnsense_client.get_firmware_update_info.return_value = {}
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("update.mock_title_firmware").state == STATE_UNAVAILABLE

    mock_opnsense_client.get_firmware_update_info.side_effect = OPNsenseConnectionError(
        "connection failed"
    )
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("update.mock_title_firmware").state == STATE_UNAVAILABLE
