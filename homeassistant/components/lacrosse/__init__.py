"""The LaCrosse integration."""

import logging
from typing import Any

import pylacrosse
from serial import SerialException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_BAUD,
    CONF_DATARATE,
    CONF_FREQUENCY,
    CONF_JEELINK_LED,
    CONF_TOGGLE_INTERVAL,
    CONF_TOGGLE_MASK,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type LaCrosseConfigEntry = ConfigEntry[pylacrosse.LaCrosse]


async def async_setup_entry(hass: HomeAssistant, entry: LaCrosseConfigEntry) -> bool:
    """Set up LaCrosse from a config entry."""
    try:
        lacrosse = await hass.async_add_executor_job(_create_lacrosse, dict(entry.data))
    except SerialException as exc:
        raise ConfigEntryNotReady(f"Unable to open serial port: {exc}") from exc

    async def _async_close(*_: object) -> None:
        await hass.async_add_executor_job(lacrosse.close)

    entry.runtime_data = lacrosse
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close)
    )
    entry.async_on_unload(_async_close)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: HomeAssistant, entry: LaCrosseConfigEntry) -> None:
    """Reload the receiver when its configuration or sensor subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: LaCrosseConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Remove a sensor's configuration through its device page."""
    if (
        subentry_id := device_entry.config_subentry_id
    ) is None or subentry_id not in entry.subentries:
        return False
    hass.config_entries.async_remove_subentry(entry, subentry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LaCrosseConfigEntry) -> bool:
    """Unload a LaCrosse config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _create_lacrosse(config: dict[str, Any]) -> pylacrosse.LaCrosse:
    """Open and configure a LaCrosse receiver."""
    usb_device: str = config[CONF_DEVICE]
    baud: int = config[CONF_BAUD]

    _LOGGER.debug("%s %s", usb_device, baud)

    lacrosse = pylacrosse.LaCrosse(usb_device, baud)
    lacrosse.open()

    try:
        if (led := config.get(CONF_JEELINK_LED)) is not None:
            lacrosse.led_mode_state(led)
        if (frequency := config.get(CONF_FREQUENCY)) is not None:
            lacrosse.set_frequency(frequency)
        if (datarate := config.get(CONF_DATARATE)) is not None:
            lacrosse.set_datarate(datarate)
        if (toggle_interval := config.get(CONF_TOGGLE_INTERVAL)) is not None:
            lacrosse.set_toggle_interval(toggle_interval)
        if (toggle_mask := config.get(CONF_TOGGLE_MASK)) is not None:
            lacrosse.set_toggle_mask(toggle_mask)

        lacrosse.start_scan()
    except SerialException:
        lacrosse.close()
        raise

    return lacrosse
