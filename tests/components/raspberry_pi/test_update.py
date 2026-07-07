"""Test the Raspberry Pi firmware update entity."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiohasupervisor import SupervisorError, SupervisorNotFoundError
from aiohasupervisor.models import RaspberryPiFirmwareInfo
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.hassio import DOMAIN as HASSIO_DOMAIN, HassioNotReadyError
from homeassistant.components.raspberry_pi.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import PLATFORM_NOT_READY_BASE_WAIT_TIME
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockModule,
    async_fire_time_changed,
    mock_integration,
)

RPI_FIRMWARE_ENTITY_ID = "update.raspberry_pi_5_firmware"


@pytest.fixture(autouse=True)
def mock_rpi_power() -> Generator[None]:
    """Mock the rpi_power integration."""
    with patch(
        "homeassistant.components.rpi_power.async_setup_entry",
        return_value=True,
    ):
        yield


async def _setup_rpi(hass: HomeAssistant, board: str) -> None:
    """Set up the raspberry_pi config entry on a given board."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    config_entry = MockConfigEntry(data={}, domain=DOMAIN, title="Raspberry Pi")
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.raspberry_pi.get_os_info",
            return_value={"board": board},
        ),
        patch(
            "homeassistant.components.raspberry_pi.update.get_os_info",
            return_value={"board": board},
        ),
        patch("homeassistant.components.rpi_power.config_flow.new_under_voltage"),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_rpi_firmware_update_entity(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> None:
    """The firmware update entity is created on its own RPi board device."""
    supervisor_client.os.raspberry_pi_firmware_info.return_value = (
        RaspberryPiFirmwareInfo(
            current_version="1765222194",
            latest_version="1778498402",
            update_available=True,
            update_blocked=False,
            update_pending=False,
            blocked_reason=None,
        )
    )
    await _setup_rpi(hass, "rpi5-64")

    state = hass.states.get(RPI_FIRMWARE_ENTITY_ID)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["installed_version"] == "2025-12-08"
    assert state.attributes["latest_version"] == "2026-05-11"
    assert (
        state.attributes["release_url"]
        == "https://github.com/raspberrypi/rpi-eeprom/blob/master/firmware-2712/release-notes.md"
    )


async def test_rpi_firmware_entity_absent_on_older_supervisor(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> None:
    """No entity when the Supervisor doesn't expose the endpoint (404)."""
    supervisor_client.os.raspberry_pi_firmware_info.side_effect = (
        SupervisorNotFoundError("Not found")
    )
    await _setup_rpi(hass, "rpi5-64")

    assert hass.states.get(RPI_FIRMWARE_ENTITY_ID) is None


async def test_rpi_firmware_entity_absent_on_unsupported_board(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> None:
    """No entity (or firmware probe) on boards without an EEPROM bootloader."""
    await _setup_rpi(hass, "rpi3-64")

    assert hass.states.get(RPI_FIRMWARE_ENTITY_ID) is None
    supervisor_client.os.raspberry_pi_firmware_info.assert_not_called()


async def test_rpi_firmware_entity_absent_when_update_blocked(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> None:
    """No entity when the update is blocked on this boot device."""
    supervisor_client.os.raspberry_pi_firmware_info.return_value = (
        RaspberryPiFirmwareInfo(
            current_version="1765222194",
            latest_version="1778498402",
            update_available=True,
            update_blocked=True,
            update_pending=False,
            blocked_reason="unsupported_boot_device",
        )
    )
    await _setup_rpi(hass, "rpi5-64")

    assert hass.states.get(RPI_FIRMWARE_ENTITY_ID) is None


async def test_rpi_firmware_platform_retries_when_os_info_unavailable(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The platform retries and recovers once the OS info becomes available."""
    supervisor_client.os.raspberry_pi_firmware_info.return_value = (
        RaspberryPiFirmwareInfo(
            current_version="1765222194",
            latest_version="1778498402",
            update_available=True,
            update_blocked=False,
            update_pending=False,
            blocked_reason=None,
        )
    )
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    config_entry = MockConfigEntry(data={}, domain=DOMAIN, title="Raspberry Pi")
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.raspberry_pi.get_os_info",
            return_value={"board": "rpi5-64"},
        ),
        patch(
            "homeassistant.components.raspberry_pi.update.get_os_info",
            side_effect=HassioNotReadyError,
        ) as mock_update_os_info,
        patch("homeassistant.components.rpi_power.config_flow.new_under_voltage"),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # First attempt fails: OS info isn't ready, so no entity is created yet.
        # The PlatformNotReady message comes from the supervisor_not_ready
        # translation.
        assert hass.states.get(RPI_FIRMWARE_ENTITY_ID) is None
        assert "Supervisor is not ready" in caplog.text

        # Once the OS info is available, the scheduled retry creates the entity.
        mock_update_os_info.side_effect = None
        mock_update_os_info.return_value = {"board": "rpi5-64"}
        freezer.tick(timedelta(seconds=PLATFORM_NOT_READY_BASE_WAIT_TIME + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get(RPI_FIRMWARE_ENTITY_ID) is not None


async def test_rpi_firmware_install_success(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> None:
    """Installing reports the new version as installed once it is applied."""
    supervisor_client.os.raspberry_pi_firmware_info.return_value = (
        RaspberryPiFirmwareInfo(
            current_version="1765222194",
            latest_version="1778498402",
            update_available=True,
            update_blocked=False,
            update_pending=False,
            blocked_reason=None,
        )
    )
    await _setup_rpi(hass, "rpi5-64")

    state = hass.states.get(RPI_FIRMWARE_ENTITY_ID)
    assert state is not None
    assert state.state == "on"

    # After the flash the Supervisor reports the update as pending (applied,
    # awaiting reboot), so the entity should read "up to date".
    supervisor_client.os.raspberry_pi_firmware_info.return_value = (
        RaspberryPiFirmwareInfo(
            current_version="1765222194",
            latest_version="1778498402",
            update_available=False,
            update_blocked=False,
            update_pending=True,
            blocked_reason=None,
        )
    )
    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": RPI_FIRMWARE_ENTITY_ID},
        blocking=True,
    )

    supervisor_client.os.update_raspberry_pi_firmware.assert_awaited_once()
    state = hass.states.get(RPI_FIRMWARE_ENTITY_ID)
    assert state is not None
    assert state.state == "off"
    assert state.attributes["installed_version"] == "2026-05-11"
    assert state.attributes["latest_version"] == "2026-05-11"


async def test_rpi_firmware_install_failure(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> None:
    """A failed update is surfaced to the user as a HomeAssistantError."""
    supervisor_client.os.raspberry_pi_firmware_info.return_value = (
        RaspberryPiFirmwareInfo(
            current_version="1765222194",
            latest_version="1778498402",
            update_available=True,
            update_blocked=False,
            update_pending=False,
            blocked_reason=None,
        )
    )
    await _setup_rpi(hass, "rpi5-64")

    supervisor_client.os.update_raspberry_pi_firmware.side_effect = SupervisorError(
        "boom"
    )
    with pytest.raises(
        HomeAssistantError, match="Error updating Raspberry Pi firmware"
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": RPI_FIRMWARE_ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(RPI_FIRMWARE_ENTITY_ID)
    assert state is not None
    assert state.state == "on"


async def test_rpi_firmware_install_refresh_failure_keeps_previous_info(
    hass: HomeAssistant,
    supervisor_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed info refresh after a successful update is logged, not raised."""
    supervisor_client.os.raspberry_pi_firmware_info.return_value = (
        RaspberryPiFirmwareInfo(
            current_version="1765222194",
            latest_version="1778498402",
            update_available=True,
            update_blocked=False,
            update_pending=False,
            blocked_reason=None,
        )
    )
    await _setup_rpi(hass, "rpi5-64")

    # The update call succeeds, but the follow-up info refresh fails.
    supervisor_client.os.raspberry_pi_firmware_info.side_effect = SupervisorError(
        "boom"
    )
    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": RPI_FIRMWARE_ENTITY_ID},
        blocking=True,
    )

    supervisor_client.os.update_raspberry_pi_firmware.assert_awaited_once()
    state = hass.states.get(RPI_FIRMWARE_ENTITY_ID)
    assert state is not None
    assert state.state == "on"
    assert "Failed to refresh Raspberry Pi firmware info" in caplog.text
