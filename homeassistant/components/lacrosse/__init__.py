"""The LaCrosse integration."""

import logging

import pylacrosse
from serial import SerialException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LaCrosseConfigEntry) -> bool:
    """Unload a LaCrosse config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _create_lacrosse(config: ConfigType) -> pylacrosse.LaCrosse:
    """Open and configure a LaCrosse receiver."""
    usb_device: str = config[CONF_DEVICE]
    baud: int = config[CONF_BAUD]

    _LOGGER.debug("%s %s", usb_device, baud)

    lacrosse = pylacrosse.LaCrosse(usb_device, baud)
    lacrosse.open()

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
    return lacrosse
