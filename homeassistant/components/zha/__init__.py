"""Support for Zigbee Home Automation devices."""
import asyncio
import contextlib
import copy
import logging
import os
import re

import voluptuous as vol
from zhaquirks import setup as setup_quirks
from zigpy.config import CONF_DEVICE, CONF_DEVICE_PATH

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType

from . import repairs, websocket_api
from .core import ZHAGateway
from .core.const import (
    BAUD_RATES,
    CONF_BAUDRATE,
    CONF_CUSTOM_QUIRKS_PATH,
    CONF_DATABASE,
    CONF_DEVICE_CONFIG,
    CONF_ENABLE_QUIRKS,
    CONF_RADIO_TYPE,
    CONF_USB_PATH,
    CONF_ZIGPY,
    DATA_ZHA,
    DOMAIN,
    PLATFORMS,
    SIGNAL_ADD_ENTITIES,
    RadioType,
)
from .core.device import get_device_automation_triggers
from .core.discovery import GROUP_PROBE
from .core.helpers import ZHAData, get_zha_data
from .radio_manager import ZhaRadioManager

DEVICE_CONFIG_SCHEMA_ENTRY = vol.Schema({vol.Optional(CONF_TYPE): cv.string})
ZHA_CONFIG_SCHEMA = {
    vol.Optional(CONF_BAUDRATE): cv.positive_int,
    vol.Optional(CONF_DATABASE): cv.string,
    vol.Optional(CONF_DEVICE_CONFIG, default={}): vol.Schema(
        {cv.string: DEVICE_CONFIG_SCHEMA_ENTRY}
    ),
    vol.Optional(CONF_ENABLE_QUIRKS, default=True): cv.boolean,
    vol.Optional(CONF_ZIGPY): dict,
    vol.Optional(CONF_RADIO_TYPE): cv.enum(RadioType),
    vol.Optional(CONF_USB_PATH): cv.string,
    vol.Optional(CONF_CUSTOM_QUIRKS_PATH): cv.isdir,
}
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(
                cv.deprecated(CONF_USB_PATH),
                cv.deprecated(CONF_BAUDRATE),
                cv.deprecated(CONF_RADIO_TYPE),
                ZHA_CONFIG_SCHEMA,
            ),
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

# Zigbee definitions
CENTICELSIUS = "C-100"

# Internal definitions
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up ZHA from config."""
    zha_data = ZHAData()
    zha_data.yaml_config = config.get(DOMAIN, {})
    hass.data[DATA_ZHA] = zha_data

    return True


def _clean_serial_port_path(path: str) -> str:
    """Clean the serial port path, applying corrections where necessary."""

    if path.startswith("socket://"):
        path = path.strip()

    # Removes extraneous brackets from IP addresses (they don't parse in CPython 3.11.4)
    if re.match(r"^socket://\[\d+\.\d+\.\d+\.\d+\]:\d+$", path):
        path = path.replace("[", "").replace("]", "")

    return path


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up ZHA.

    Will automatically load components to support devices found on the network.
    """

    # Remove brackets around IP addresses, this no longer works in CPython 3.11.4
    # This will be removed in 2023.11.0
    path = config_entry.data[CONF_DEVICE][CONF_DEVICE_PATH]
    cleaned_path = _clean_serial_port_path(path)
    data = copy.deepcopy(dict(config_entry.data))

    if path != cleaned_path:
        _LOGGER.debug("Cleaned serial port path %r -> %r", path, cleaned_path)
        data[CONF_DEVICE][CONF_DEVICE_PATH] = cleaned_path
        hass.config_entries.async_update_entry(config_entry, data=data)

    zha_data = get_zha_data(hass)

    if zha_data.yaml_config.get(CONF_ENABLE_QUIRKS, True):
        setup_quirks(
            custom_quirks_path=zha_data.yaml_config.get(CONF_CUSTOM_QUIRKS_PATH)
        )

    # temporary code to remove the ZHA storage file from disk.
    # this will be removed in 2022.10.0
    storage_path = hass.config.path(STORAGE_DIR, "zha.storage")
    if os.path.isfile(storage_path):
        _LOGGER.debug("removing ZHA storage file")
        await hass.async_add_executor_job(os.remove, storage_path)
    else:
        _LOGGER.debug("ZHA storage file does not exist or was already removed")

    # Load and cache device trigger information early
    device_registry = dr.async_get(hass)
    radio_mgr = ZhaRadioManager.from_config_entry(hass, config_entry)

    async with radio_mgr.connect_zigpy_app() as app:
        for dev in app.devices.values():
            dev_entry = device_registry.async_get_device(
                identifiers={(DOMAIN, str(dev.ieee))},
                connections={(dr.CONNECTION_ZIGBEE, str(dev.ieee))},
            )

            if dev_entry is None:
                continue

            zha_data.device_trigger_cache[dev_entry.id] = (
                str(dev.ieee),
                get_device_automation_triggers(dev),
            )

    _LOGGER.debug("Trigger cache: %s", zha_data.device_trigger_cache)

    zha_gateway = ZHAGateway(hass, zha_data.yaml_config, config_entry)

    async def async_zha_shutdown():
        """Handle shutdown tasks."""
        await zha_gateway.shutdown()
        # clean up any remaining entity metadata
        # (entities that have been discovered but not yet added to HA)
        # suppress KeyError because we don't know what state we may
        # be in when we get here in failure cases
        with contextlib.suppress(KeyError):
            for platform in PLATFORMS:
                del zha_data.platforms[platform]

    config_entry.async_on_unload(async_zha_shutdown)

    try:
        await zha_gateway.async_initialize()
    except Exception:  # pylint: disable=broad-except
        if RadioType[config_entry.data[CONF_RADIO_TYPE]] == RadioType.ezsp:
            try:
                await repairs.warn_on_wrong_silabs_firmware(
                    hass, config_entry.data[CONF_DEVICE][CONF_DEVICE_PATH]
                )
            except repairs.AlreadyRunningEZSP as exc:
                # If connecting fails but we somehow probe EZSP (e.g. stuck in the
                # bootloader), reconnect, it should work
                raise ConfigEntryNotReady from exc

        raise

    repairs.async_delete_blocking_issues(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_ZIGBEE, str(zha_gateway.coordinator_ieee))},
        identifiers={(DOMAIN, str(zha_gateway.coordinator_ieee))},
        name="Zigbee Coordinator",
        manufacturer="ZHA",
        model=zha_gateway.radio_description,
    )

    websocket_api.async_load_api(hass)

    await zha_gateway.async_initialize_devices_and_entities()
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    async_dispatcher_send(hass, SIGNAL_ADD_ENTITIES)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload ZHA config entry."""
    zha_data = get_zha_data(hass)
    zha_data.gateway = None

    GROUP_PROBE.cleanup()
    websocket_api.async_unload_api(hass)

    # our components don't have unload methods so no need to look at return values
    await asyncio.gather(
        *(
            hass.config_entries.async_forward_entry_unload(config_entry, platform)
            for platform in PLATFORMS
        )
    )

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        data = {
            CONF_RADIO_TYPE: config_entry.data[CONF_RADIO_TYPE],
            CONF_DEVICE: {CONF_DEVICE_PATH: config_entry.data[CONF_USB_PATH]},
        }

        baudrate = get_zha_data(hass).yaml_config.get(CONF_BAUDRATE)
        if data[CONF_RADIO_TYPE] != RadioType.deconz and baudrate in BAUD_RATES:
            data[CONF_DEVICE][CONF_BAUDRATE] = baudrate

        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=data)

    if config_entry.version == 2:
        data = {**config_entry.data}

        if data[CONF_RADIO_TYPE] == "ti_cc":
            data[CONF_RADIO_TYPE] = "znp"

        config_entry.version = 3
        hass.config_entries.async_update_entry(config_entry, data=data)

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True
