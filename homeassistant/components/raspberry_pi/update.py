"""Raspberry Pi firmware update entity."""

from aiohasupervisor import SupervisorError

from homeassistant.components.hassio import HassioNotReadyError, get_os_info
from homeassistant.components.homeassistant_hardware.update import (
    RaspberryPiFirmwareUpdateEntity,
)
from homeassistant.components.homeassistant_hardware.util import (
    BOARDS_WITH_RASPBERRYPI_FIRMWARE,
    async_get_raspberry_pi_firmware_info,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .hardware import BOARD_NAMES, MODELS


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Raspberry Pi firmware update entity."""
    try:
        os_info = get_os_info(hass)
    except HassioNotReadyError as err:
        raise PlatformNotReady(
            translation_domain=DOMAIN,
            translation_key="supervisor_not_ready",
        ) from err

    board = os_info.get("board")

    # Only RPi 4/5 expose the bootloader EEPROM. The Yellow's CM4/CM5 is handled
    # by the homeassistant_yellow integration on its own device.
    if board is None or board not in BOARDS_WITH_RASPBERRYPI_FIRMWARE:
        return

    try:
        firmware = await async_get_raspberry_pi_firmware_info(hass)
    except SupervisorError as err:
        raise PlatformNotReady(
            f"Error fetching Raspberry Pi firmware info: {err}"
        ) from err

    # Skip when the update is blocked on this boot device (e.g. CM4 without
    # flashrom updates enabled). The blocked state is surfaced as a repair.
    if firmware is None or firmware.update_blocked:
        return

    device_info = DeviceInfo(
        identifiers={(DOMAIN, board)},
        manufacturer="Raspberry Pi",
        model=MODELS.get(board),
        name=BOARD_NAMES.get(board, "Raspberry Pi"),
    )
    async_add_entities(
        [
            RaspberryPiFirmwareUpdateEntity(
                firmware, device_info, unique_id=f"{board}_rpi_firmware", board=board
            )
        ]
    )
