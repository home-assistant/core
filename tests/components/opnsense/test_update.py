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
