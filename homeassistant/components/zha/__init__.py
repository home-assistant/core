"""Support for Zigbee Home Automation devices."""

import asyncio
import contextlib
import copy
import logging
import re

import voluptuous as vol
from zhaquirks import setup as setup_quirks
from zigpy.config import CONF_DATABASE, CONF_DEVICE, CONF_DEVICE_PATH
from zigpy.exceptions import NetworkSettingsInconsistent, TransientConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from . import repairs, websocket_api
from .core import ZHAGateway
from .core.const import (
    BAUD_RATES,
    CONF_BAUDRATE,
    CONF_CUSTOM_QUIRKS_PATH,
    CONF_DEVICE_CONFIG,
    CONF_ENABLE_QUIRKS,
    CONF_FLOW_CONTROL,
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
from .repairs.network_settings_inconsistent import warn_on_inconsistent_network_settings
from .repairs.wrong_silabs_firmware import (
    AlreadyRunningEZSP,
    warn_on_wrong_silabs_firmware,
)

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
        await hass.async_add_import_executor_job(
            setup_quirks, zha_data.yaml_config.get(CONF_CUSTOM_QUIRKS_PATH)
        )

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

    try:
        zha_gateway = await ZHAGateway.async_from_config(
            hass=hass,
            config=zha_data.yaml_config,
            config_entry=config_entry,
        )
    except NetworkSettingsInconsistent as exc:
        await warn_on_inconsistent_network_settings(
            hass,
            config_entry=config_entry,
            old_state=exc.old_state,
            new_state=exc.new_state,
        )
        raise ConfigEntryError(
            "Network settings do not match most recent backup"
        ) from exc
    except TransientConnectionError as exc:
        raise ConfigEntryNotReady from exc
    except Exception as exc:
        _LOGGER.debug("Failed to set up ZHA", exc_info=exc)
        device_path = config_entry.data[CONF_DEVICE][CONF_DEVICE_PATH]

        if (
            not device_path.startswith("socket://")
            and RadioType[config_entry.data[CONF_RADIO_TYPE]] == RadioType.ezsp
        ):
            try:
                # Ignore all exceptions during probing, they shouldn't halt setup
                if await warn_on_wrong_silabs_firmware(hass, device_path):
                    raise ConfigEntryError("Incorrect firmware installed") from exc
            except AlreadyRunningEZSP as ezsp_exc:
                raise ConfigEntryNotReady from ezsp_exc

        raise ConfigEntryNotReady from exc

    repairs.async_delete_blocking_issues(hass)

    manufacturer = zha_gateway.state.node_info.manufacturer
    model = zha_gateway.state.node_info.model

    if manufacturer is None and model is None:
        manufacturer = "Unknown"
        model = "Unknown"

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_ZIGBEE, str(zha_gateway.state.node_info.ieee))},
        identifiers={(DOMAIN, str(zha_gateway.state.node_info.ieee))},
        name="Zigbee Coordinator",
        manufacturer=manufacturer,
        model=model,
        sw_version=zha_gateway.state.node_info.version,
    )

    websocket_api.async_load_api(hass)

    async def async_shutdown(_: Event) -> None:
        await zha_gateway.shutdown()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_shutdown)
    )

    await zha_gateway.async_initialize_devices_and_entities()
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    async_dispatcher_send(hass, SIGNAL_ADD_ENTITIES)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload ZHA config entry."""
    zha_data = get_zha_data(hass)

    if zha_data.gateway is not None:
        await zha_data.gateway.shutdown()
        zha_data.gateway = None

    # clean up any remaining entity metadata
    # (entities that have been discovered but not yet added to HA)
    # suppress KeyError because we don't know what state we may
    # be in when we get here in failure cases
    with contextlib.suppress(KeyError):
        for platform in PLATFORMS:
            del zha_data.platforms[platform]

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

        hass.config_entries.async_update_entry(config_entry, data=data, version=2)

    if config_entry.version == 2:
        data = {**config_entry.data}

        if data[CONF_RADIO_TYPE] == "ti_cc":
            data[CONF_RADIO_TYPE] = "znp"

        hass.config_entries.async_update_entry(config_entry, data=data, version=3)

    if config_entry.version == 3:
        data = {**config_entry.data}

        if not data[CONF_DEVICE].get(CONF_BAUDRATE):
            data[CONF_DEVICE][CONF_BAUDRATE] = {
                "deconz": 38400,
                "xbee": 57600,
                "ezsp": 57600,
                "znp": 115200,
                "zigate": 115200,
            }[data[CONF_RADIO_TYPE]]

        if not data[CONF_DEVICE].get(CONF_FLOW_CONTROL):
            data[CONF_DEVICE][CONF_FLOW_CONTROL] = None

        hass.config_entries.async_update_entry(config_entry, data=data, version=4)

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True
