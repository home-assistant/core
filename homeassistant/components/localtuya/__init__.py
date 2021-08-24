"""The LocalTuya integration integration.

Sample YAML config with all supported entity types (default values
are pre-filled for optional fields):

localtuya:
  - host: 192.168.1.x
    device_id: xxxxx
    local_key: xxxxx
    friendly_name: Tuya Device
    protocol_version: "3.3"
    entities:
      - platform: binary_sensor
        friendly_name: Plug Status
        id: 1
        device_class: power
        state_on: "true" # Optional
        state_off: "false" # Optional

      - platform: cover
        friendly_name: Device Cover
        id: 2
        commands_set: # Optional, default: "on_off_stop"
            ["on_off_stop","open_close_stop","fz_zz_stop","1_2_3"]
        positioning_mode: ["none","position","timed"] # Optional, default: "none"
        currpos_dp: 3 # Optional, required only for "position" mode
        setpos_dp: 4  # Optional, required only for "position" mode
        position_inverted: [True,False] # Optional, default: False
        span_time: 25 # Full movement time: Optional, required only for "timed" mode

      - platform: fan
        friendly_name: Device Fan
        id: 3

      - platform: light
        friendly_name: Device Light
        id: 4
        brightness: 20
        brightness_lower: 29 # Optional
        brightness_upper: 1000 # Optional
        color_temp: 21

      - platform: sensor
        friendly_name: Plug Voltage
        id: 20
        scaling: 0.1 # Optional
        device_class: voltage # Optional
        unit_of_measurement: "V" # Optional

      - platform: switch
        friendly_name: Plug
        id: 1
        current: 18 # Optional
        current_consumption: 19 # Optional
        voltage: 20 # Optional
"""
import asyncio
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.entity_registry as er
import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_ID,
    CONF_PLATFORM,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.reload import async_integration_yaml_config

from .common import TuyaDevice, async_config_entry_by_device_id
from .config_flow import config_schema
from .const import CONF_PRODUCT_KEY, DATA_DISCOVERY, DOMAIN, TUYA_DEVICE
from .discovery import TuyaDiscovery

_LOGGER = logging.getLogger(__name__)

UNSUB_LISTENER = "unsub_listener"

RECONNECT_INTERVAL = timedelta(seconds=60)

CONFIG_SCHEMA = config_schema()

CONF_DP = "dp"
CONF_VALUE = "value"

SERVICE_SET_DP = "set_dp"
SERVICE_SET_DP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_DP): int,
        vol.Required(CONF_VALUE): object,
    }
)


@callback
def _async_update_config_entry_if_from_yaml(hass, entries_by_id, conf):
    """Update a config entry with the latest yaml."""
    device_id = conf[CONF_DEVICE_ID]

    if device_id in entries_by_id and entries_by_id[device_id].source == SOURCE_IMPORT:
        entry = entries_by_id[device_id]
        hass.config_entries.async_update_entry(entry, data=conf.copy())


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the LocalTuya integration component."""
    hass.data.setdefault(DOMAIN, {})

    device_cache = {}

    async def _handle_reload(service):
        """Handle reload service call."""
        config = await async_integration_yaml_config(hass, DOMAIN)

        if not config or DOMAIN not in config:
            return

        current_entries = hass.config_entries.async_entries(DOMAIN)
        entries_by_id = {entry.data[CONF_DEVICE_ID]: entry for entry in current_entries}

        for conf in config[DOMAIN]:
            _async_update_config_entry_if_from_yaml(hass, entries_by_id, conf)

        reload_tasks = [
            hass.config_entries.async_reload(entry.entry_id)
            for entry in current_entries
        ]

        await asyncio.gather(*reload_tasks)

    async def _handle_set_dp(event):
        """Handle set_dp service call."""
        entry = async_config_entry_by_device_id(hass, event.data[CONF_DEVICE_ID])
        if not entry:
            raise HomeAssistantError("unknown device id")

        if entry.entry_id not in hass.data[DOMAIN]:
            raise HomeAssistantError("device has not been discovered")

        device = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE]
        if not device.connected:
            raise HomeAssistantError("not connected to device")

        await device.set_dp(event.data[CONF_VALUE], event.data[CONF_DP])

    def _device_discovered(device):
        """Update address of device if it has changed."""
        device_ip = device["ip"]
        device_id = device["gwId"]
        product_key = device["productKey"]

        # If device is not in cache, check if a config entry exists
        if device_id not in device_cache:
            entry = async_config_entry_by_device_id(hass, device_id)
            if entry:
                # Save address from config entry in cache to trigger
                # potential update below
                device_cache[device_id] = entry.data[CONF_HOST]

        if device_id not in device_cache:
            return

        entry = async_config_entry_by_device_id(hass, device_id)
        if entry is None:
            return

        updates = {}

        if device_cache[device_id] != device_ip:
            updates[CONF_HOST] = device_ip
            device_cache[device_id] = device_ip

        if entry.data.get(CONF_PRODUCT_KEY) != product_key:
            updates[CONF_PRODUCT_KEY] = product_key

        # Update settings if something changed, otherwise try to connect. Updating
        # settings triggers a reload of the config entry, which tears down the device
        # so no need to connect in that case.
        if updates:
            _LOGGER.debug("Update keys for device %s: %s", device_id, updates)
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, **updates}
            )
        elif entry.entry_id in hass.data[DOMAIN]:
            _LOGGER.debug("Device %s found with IP %s", device_id, device_ip)

            device = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE]
            device.async_connect()

    discovery = TuyaDiscovery(_device_discovered)

    def _shutdown(event):
        """Clean up resources when shutting down."""
        discovery.close()

    try:
        await discovery.start()
        hass.data[DOMAIN][DATA_DISCOVERY] = discovery
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("failed to set up discovery")

    async def _async_reconnect(now):
        """Try connecting to devices not already connected to."""
        for entry_id, value in hass.data[DOMAIN].items():
            if entry_id == DATA_DISCOVERY:
                continue

            device = value[TUYA_DEVICE]
            if not device.connected:
                device.async_connect()

    async_track_time_interval(hass, _async_reconnect, RECONNECT_INTERVAL)

    hass.helpers.service.async_register_admin_service(
        DOMAIN,
        SERVICE_RELOAD,
        _handle_reload,
    )

    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_SET_DP, _handle_set_dp, schema=SERVICE_SET_DP_SCHEMA
    )

    for host_config in config.get(DOMAIN, []):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=host_config
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up LocalTuya integration from a config entry."""
    unsub_listener = entry.add_update_listener(update_listener)

    device = TuyaDevice(hass, entry.data)

    hass.data[DOMAIN][entry.entry_id] = {
        UNSUB_LISTENER: unsub_listener,
        TUYA_DEVICE: device,
    }

    async def setup_entities():
        platforms = set(entity[CONF_PLATFORM] for entity in entry.data[CONF_ENTITIES])
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(entry, platform)
                for platform in platforms
            ]
        )
        device.async_connect()

    await async_remove_orphan_entities(hass, entry)

    hass.async_create_task(setup_entities())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in set(
                    entity[CONF_PLATFORM] for entity in entry.data[CONF_ENTITIES]
                )
            ]
        )
    )

    hass.data[DOMAIN][entry.entry_id][UNSUB_LISTENER]()
    await hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE].close()
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return True


async def update_listener(hass, config_entry):
    """Update listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_remove_orphan_entities(hass, entry):
    """Remove entities associated with config entry that has been removed."""
    ent_reg = await er.async_get_registry(hass)
    entities = {
        int(ent.unique_id.split("_")[-1]): ent.entity_id
        for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    }

    for entity in entry.data[CONF_ENTITIES]:
        if entity[CONF_ID] in entities:
            del entities[entity[CONF_ID]]

    for entity_id in entities.values():
        ent_reg.async_remove(entity_id)
