"""Tests for OPNsense firmware updates."""

from asyncio import Event
from datetime import timedelta
from unittest.mock import AsyncMock

from aiopnsense import OPNsenseConnectionError, OPNsensePrivilegeMissing
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.opnsense.const import (
    DOMAIN,
    get_firmware_privilege_issue_id,
)
from homeassistant.components.update import DATA_COMPONENT
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator


@pytest.mark.parametrize(
    ("latest", "status", "expected_state"),
    [
        pytest.param("25.7.8", None, "off", id="no-new-version"),
        pytest.param("25.7.9", "update", "on", id="installable-update"),
    ],
)
async def test_firmware_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    latest: str,
    status: str | None,
    expected_state: str,
) -> None:
    """Test the firmware update entity reports available updates."""
    mock_opnsense_client.get_firmware_update_info.return_value["product"][
        "product_latest"
    ] = latest
    mock_opnsense_client.get_firmware_update_info.return_value["status"] = status

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert state.state == expected_state
    assert state.attributes["installed_version"] == "25.7.8"
    assert state.attributes["latest_version"] == latest
    mock_opnsense_client.get_firmware_update_info.assert_awaited_once()
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "mocked_unique_id"), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.configuration_url == "http://router.lan/"


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
    ("status_reboot", "status_msg", "expected_summary"),
    [
        pytest.param(
            "0",
            "There are 15 updates available.",
            "There are 15 updates available.",
            id="no-reboot",
        ),
        pytest.param(
            "1",
            "There are 114 updates available, total download size is 319.8MiB. This update requires a reboot.",
            "There are 114 updates available, total download size is 319.8MiB. This update requires a reboot.",
            id="reboot-message-from-opnsense",
        ),
        pytest.param("1", None, None, id="reboot-fallback"),
    ],
)
async def test_firmware_update_details(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    hass_ws_client: WebSocketGenerator,
    status_reboot: str,
    status_msg: str | None,
    expected_summary: str | None,
) -> None:
    """Show OPNsense update status, reboot requirement, and changelog link."""
    mock_opnsense_client.get_firmware_update_info.return_value.update(
        {
            "status_msg": status_msg,
            "status_reboot": status_reboot,
        }
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert state.attributes.get("release_summary") == expected_summary
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


async def test_firmware_install_concurrent_calls(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
) -> None:
    """Test a pending firmware start prevents another installation."""
    request_started = Event()
    finish_request = Event()

    async def start_upgrade(*, type: str) -> dict[str, str]:
        request_started.set()
        await finish_request.wait()
        return {"status": "ok"}

    mock_opnsense_client.get_firmware_update_info.return_value["status"] = "update"
    mock_opnsense_client.upgrade_firmware.side_effect = start_upgrade
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    install_task = hass.async_create_task(
        hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.mock_title_firmware"},
            blocking=True,
        )
    )
    await request_started.wait()

    try:
        assert hass.states.get("update.mock_title_firmware").attributes["in_progress"]
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "update",
                "install",
                {"entity_id": "update.mock_title_firmware"},
                blocking=True,
            )
        mock_opnsense_client.upgrade_firmware.assert_awaited_once_with(type="update")
    finally:
        finish_request.set()
        await install_task


@pytest.mark.parametrize("terminal_status", ["done", "reboot"])
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


async def test_firmware_upgrade_retries_error_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test transient firmware errors keep upgrade polling active."""
    mock_opnsense_client.get_firmware_update_info.return_value["status"] = "update"
    mock_opnsense_client.upgrade_firmware.return_value = {"status": "ok"}
    mock_opnsense_client.upgrade_status.side_effect = [
        OPNsenseConnectionError("router is rebooting"),
        {"status": "error"},
        {"status": "done"},
    ]
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "update", "install", {"entity_id": "update.mock_title_firmware"}, blocking=True
    )

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert state.attributes["in_progress"]
    mock_opnsense_client.upgrade_status.assert_awaited_once()

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert state.attributes["in_progress"]
    assert mock_opnsense_client.upgrade_status.await_count == 2

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert not state.attributes["in_progress"]
    assert mock_opnsense_client.upgrade_status.await_count == 3


async def test_firmware_upgrade_status_polls_do_not_overlap(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
) -> None:
    """Status polling skips a tick while the previous request is in flight."""
    status_started = Event()
    status_response = Event()

    async def wait_for_status() -> dict[str, str]:
        status_started.set()
        await status_response.wait()
        return {"status": "running"}

    mock_opnsense_client.get_firmware_update_info.return_value["status"] = "update"
    mock_opnsense_client.upgrade_firmware.return_value = {"status": "ok"}
    mock_opnsense_client.upgrade_status.side_effect = wait_for_status
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "update", "install", {"entity_id": "update.mock_title_firmware"}, blocking=True
    )

    update_entity = hass.data[DATA_COMPONENT].get_entity("update.mock_title_firmware")
    assert update_entity is not None
    poll_task = hass.async_create_task(
        update_entity._async_poll_upgrade_status(
            dt_util.utcnow(), generation=update_entity._upgrade_status_generation
        )
    )
    await status_started.wait()
    await update_entity._async_poll_upgrade_status(
        dt_util.utcnow(), generation=update_entity._upgrade_status_generation
    )
    mock_opnsense_client.upgrade_status.assert_awaited_once()

    status_response.set()
    await poll_task


async def test_firmware_upgrade_refreshes_after_reboot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Retry firmware info once if OPNsense is still restarting."""
    mock_opnsense_client.get_firmware_update_info.side_effect = [
        {
            "status": "update",
            "product": {"product_version": "25.7.8", "product_latest": "25.7.8"},
        },
        OPNsenseConnectionError("router is rebooting"),
        OPNsenseConnectionError("router is still rebooting"),
        {
            "status": "update",
            "product": {"product_version": "25.7.8", "product_latest": "25.7.9"},
        },
    ]
    mock_opnsense_client.upgrade_firmware.return_value = {"status": "ok"}
    mock_opnsense_client.upgrade_status.return_value = {"status": "reboot"}
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "update", "install", {"entity_id": "update.mock_title_firmware"}, blocking=True
    )
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_opnsense_client.get_firmware_update_info.await_count == 2

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_opnsense_client.get_firmware_update_info.await_count == 3

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_opnsense_client.get_firmware_update_info.await_count == 4
    assert (
        hass.states.get("update.mock_title_firmware").attributes["latest_version"]
        == "25.7.9"
    )

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_opnsense_client.get_firmware_update_info.await_count == 4


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
    mock_opnsense_client.upgrade_status.assert_not_awaited()


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


@pytest.mark.parametrize(
    ("response", "error", "expected_error"),
    [
        pytest.param({"status": "failure"}, None, HomeAssistantError, id="rejected"),
        pytest.param(None, None, HomeAssistantError, id="empty-response"),
        pytest.param(
            None,
            OPNsenseConnectionError("connection failed"),
            OPNsenseConnectionError,
            id="connection-error",
        ),
    ],
)
async def test_firmware_install_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    response: dict[str, str] | None,
    error: OPNsenseConnectionError | None,
    expected_error: type[Exception],
) -> None:
    """Test failed firmware starts clear progress and allow a retry."""
    mock_opnsense_client.get_firmware_update_info.return_value["status"] = "update"
    mock_opnsense_client.upgrade_firmware.return_value = response
    mock_opnsense_client.upgrade_firmware.side_effect = error
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(expected_error):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.mock_title_firmware"},
            blocking=True,
        )

    assert not hass.states.get("update.mock_title_firmware").attributes["in_progress"]
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_opnsense_client.upgrade_status.assert_not_awaited()

    mock_opnsense_client.upgrade_firmware.side_effect = None
    mock_opnsense_client.upgrade_firmware.return_value = {"status": "ok"}
    await hass.services.async_call(
        "update", "install", {"entity_id": "update.mock_title_firmware"}, blocking=True
    )
    assert hass.states.get("update.mock_title_firmware").attributes["in_progress"]


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

    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert state.state == "off"
    assert state.attributes["latest_version"] == "25.7.8"

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.mock_title_firmware"},
            blocking=True,
        )

    mock_opnsense_client.upgrade_firmware.assert_not_awaited()


async def test_firmware_privilege_missing_keeps_tracker_and_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Firmware permission errors do not block trackers and clear after recovery."""
    issue_id = get_firmware_privilege_issue_id(mock_config_entry.entry_id)
    mock_opnsense_client.validate.side_effect = OPNsensePrivilegeMissing(
        "missing System: Firmware privilege"
    )
    mock_opnsense_client.get_firmware_update_info.return_value = {}

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert any(
        entity.domain == "device_tracker"
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    )
    mock_opnsense_client.get_arp_table.assert_awaited_once()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    mock_opnsense_client.validate.side_effect = None
    mock_opnsense_client.get_firmware_update_info.return_value = {
        "product": {"product_version": "25.7.8", "product_latest": "25.7.8"}
    }
    await mock_config_entry.runtime_data.update_coordinator.async_request_refresh()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_firmware_privilege_missing_issue_cleared_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Clear the persistent privilege issue when the config entry unloads."""
    issue_id = get_firmware_privilege_issue_id(mock_config_entry.entry_id)
    mock_opnsense_client.get_firmware_update_info.side_effect = (
        OPNsensePrivilegeMissing("missing System: Firmware privilege")
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_disabled_update_does_not_fetch_firmware_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A disabled firmware update entity does not poll firmware status."""
    entity_registry.async_get_or_create(
        "update",
        DOMAIN,
        "mocked_unique_id",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_opnsense_client.get_firmware_update_info.assert_not_awaited()
    mock_opnsense_client.get_arp_table.assert_awaited_once()


async def test_firmware_update_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opnsense_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test missing data and communication failures make the entity unavailable."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_opnsense_client.get_firmware_update_info.return_value = None
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_opnsense_client.get_firmware_update_info.return_value = {}
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_opnsense_client.get_firmware_update_info.side_effect = OPNsenseConnectionError(
        "connection failed"
    )
    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("update.mock_title_firmware")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
