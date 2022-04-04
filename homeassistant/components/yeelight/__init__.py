"""Support for Xiaomi Yeelight WiFi color bulb."""
from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from yeelight import BulbException
from yeelight.aio import AsyncBulb

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_ID,
    CONF_MODEL,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ACTION_OFF,
    ACTION_RECOVER,
    ACTION_STAY,
    ATTR_ACTION,
    ATTR_COUNT,
    ATTR_TRANSITIONS,
    CONF_CUSTOM_EFFECTS,
    CONF_DETECTED_MODEL,
    CONF_FLOW_PARAMS,
    CONF_MODE_MUSIC,
    CONF_NIGHTLIGHT_SWITCH,
    CONF_NIGHTLIGHT_SWITCH_TYPE,
    CONF_SAVE_ON_CHANGE,
    CONF_TRANSITION,
    DATA_CONFIG_ENTRIES,
    DATA_CUSTOM_EFFECTS,
    DATA_DEVICE,
    DEFAULT_MODE_MUSIC,
    DEFAULT_NAME,
    DEFAULT_NIGHTLIGHT_SWITCH,
    DEFAULT_SAVE_ON_CHANGE,
    DEFAULT_TRANSITION,
    DOMAIN,
    NIGHTLIGHT_SWITCH_TYPE_LIGHT,
    PLATFORMS,
    YEELIGHT_HSV_TRANSACTION,
    YEELIGHT_RGB_TRANSITION,
    YEELIGHT_SLEEP_TRANSACTION,
    YEELIGHT_TEMPERATURE_TRANSACTION,
)
from .device import YeelightDevice, async_format_id
from .scanner import YeelightScanner

_LOGGER = logging.getLogger(__name__)


YEELIGHT_FLOW_TRANSITION_SCHEMA = {
    vol.Optional(ATTR_COUNT, default=0): cv.positive_int,
    vol.Optional(ATTR_ACTION, default=ACTION_RECOVER): vol.Any(
        ACTION_RECOVER, ACTION_OFF, ACTION_STAY
    ),
    vol.Required(ATTR_TRANSITIONS): [
        {
            vol.Exclusive(YEELIGHT_RGB_TRANSITION, CONF_TRANSITION): vol.All(
                cv.ensure_list, [cv.positive_int]
            ),
            vol.Exclusive(YEELIGHT_HSV_TRANSACTION, CONF_TRANSITION): vol.All(
                cv.ensure_list, [cv.positive_int]
            ),
            vol.Exclusive(YEELIGHT_TEMPERATURE_TRANSACTION, CONF_TRANSITION): vol.All(
                cv.ensure_list, [cv.positive_int]
            ),
            vol.Exclusive(YEELIGHT_SLEEP_TRANSACTION, CONF_TRANSITION): vol.All(
                cv.ensure_list, [cv.positive_int]
            ),
        }
    ],
}

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TRANSITION, default=DEFAULT_TRANSITION): cv.positive_int,
        vol.Optional(CONF_MODE_MUSIC, default=False): cv.boolean,
        vol.Optional(CONF_SAVE_ON_CHANGE, default=False): cv.boolean,
        vol.Optional(CONF_NIGHTLIGHT_SWITCH_TYPE): vol.Any(
            NIGHTLIGHT_SWITCH_TYPE_LIGHT
        ),
        vol.Optional(CONF_MODEL): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
                vol.Optional(CONF_CUSTOM_EFFECTS): [
                    {
                        vol.Required(CONF_NAME): cv.string,
                        vol.Required(CONF_FLOW_PARAMS): YEELIGHT_FLOW_TRANSITION_SCHEMA,
                    }
                ],
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Yeelight bulbs."""
    conf = config.get(DOMAIN, {})
    hass.data[DOMAIN] = {
        DATA_CUSTOM_EFFECTS: conf.get(CONF_CUSTOM_EFFECTS, {}),
        DATA_CONFIG_ENTRIES: {},
    }
    # Make sure the scanner is always started in case we are
    # going to retry via ConfigEntryNotReady and the bulb has changed
    # ip
    scanner = YeelightScanner.async_get(hass)
    await scanner.async_setup()

    # Import manually configured devices
    for host, device_config in config.get(DOMAIN, {}).get(CONF_DEVICES, {}).items():
        _LOGGER.debug("Importing configured %s", host)
        entry_config = {CONF_HOST: host, **device_config}
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_config
            )
        )

    return True


async def _async_initialize(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: YeelightDevice,
) -> None:
    entry_data = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][entry.entry_id] = {}
    await device.async_setup()
    entry_data[DATA_DEVICE] = device

    if (
        device.capabilities
        and entry.data.get(CONF_DETECTED_MODEL) != device.capabilities["model"]
    ):
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_DETECTED_MODEL: device.capabilities["model"]},
        )


@callback
def _async_normalize_config_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Move options from data for imported entries.

    Initialize options with default values for other entries.

    Copy the unique id to CONF_ID if it is missing
    """
    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_HOST: entry.data.get(CONF_HOST),
                CONF_ID: entry.data.get(CONF_ID) or entry.unique_id,
                CONF_DETECTED_MODEL: entry.data.get(CONF_DETECTED_MODEL),
            },
            options={
                CONF_NAME: entry.data.get(CONF_NAME, ""),
                CONF_MODEL: entry.data.get(
                    CONF_MODEL, entry.data.get(CONF_DETECTED_MODEL, "")
                ),
                CONF_TRANSITION: entry.data.get(CONF_TRANSITION, DEFAULT_TRANSITION),
                CONF_MODE_MUSIC: entry.data.get(CONF_MODE_MUSIC, DEFAULT_MODE_MUSIC),
                CONF_SAVE_ON_CHANGE: entry.data.get(
                    CONF_SAVE_ON_CHANGE, DEFAULT_SAVE_ON_CHANGE
                ),
                CONF_NIGHTLIGHT_SWITCH: entry.data.get(
                    CONF_NIGHTLIGHT_SWITCH, DEFAULT_NIGHTLIGHT_SWITCH
                ),
            },
            unique_id=entry.unique_id or entry.data.get(CONF_ID),
        )
    elif entry.unique_id and not entry.data.get(CONF_ID):
        hass.config_entries.async_update_entry(
            entry,
            data={CONF_HOST: entry.data.get(CONF_HOST), CONF_ID: entry.unique_id},
        )
    elif entry.data.get(CONF_ID) and not entry.unique_id:
        hass.config_entries.async_update_entry(
            entry,
            unique_id=entry.data[CONF_ID],
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yeelight from a config entry."""
    _async_normalize_config_entry(hass, entry)

    if not entry.data.get(CONF_HOST):
        bulb_id = async_format_id(entry.data.get(CONF_ID, entry.unique_id))
        raise ConfigEntryNotReady(f"Waiting for {bulb_id} to be discovered")

    try:
        device = await _async_get_device(hass, entry.data[CONF_HOST], entry)
        await _async_initialize(hass, entry, device)
    except (asyncio.TimeoutError, OSError, BulbException) as ex:
        raise ConfigEntryNotReady from ex

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    # Wait to install the reload listener until everything was successfully initialized
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data_config_entries = hass.data[DOMAIN][DATA_CONFIG_ENTRIES]
    data_config_entries.pop(entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_get_device(
    hass: HomeAssistant, host: str, entry: ConfigEntry
) -> YeelightDevice:
    # Get model from config and capabilities
    model = entry.options.get(CONF_MODEL) or entry.data.get(CONF_DETECTED_MODEL)

    # Set up device
    bulb = AsyncBulb(host, model=model or None)

    device = YeelightDevice(hass, host, {**entry.options, **entry.data}, bulb)
    # start listening for local pushes
    await device.bulb.async_listen(device.async_update_callback)

    # register stop callback to shutdown listening for local pushes
    async def async_stop_listen_task(event):
        """Stop listen task."""
        _LOGGER.debug("Shutting down Yeelight Listener (stop event)")
        await device.bulb.async_stop_listening()

    @callback
    def _async_stop_listen_on_unload():
        """Stop listen task."""
        _LOGGER.debug("Shutting down Yeelight Listener (unload)")
        hass.async_create_task(device.bulb.async_stop_listening())

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_listen_task)
    )
    entry.async_on_unload(_async_stop_listen_on_unload)

    # fetch initial state
    await device.async_update()

    if (
        # Must have last_properties
        not device.bulb.last_properties
        # Must have at least a power property
        or (
            "main_power" not in device.bulb.last_properties
            and "power" not in device.bulb.last_properties
        )
    ):
        raise ConfigEntryNotReady(
            "Could not fetch initial state; try power cycling the device"
        )

    return device
