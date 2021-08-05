"""Component to embed TP-Link smart home devices."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import time
from typing import Any

from pyHS100.smartdevice import SmartDevice, SmartDeviceException
from pyHS100.smartplug import SmartPlug
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import ATTR_LAST_RESET
from homeassistant.components.switch import ATTR_CURRENT_POWER_W, ATTR_TODAY_ENERGY_KWH
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_VOLTAGE,
    CONF_ALIAS,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_STATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utc_from_timestamp

from .common import SmartDevices, async_discover_devices, get_static_devices
from .const import (
    ATTR_CONFIG,
    ATTR_CURRENT_A,
    ATTR_TOTAL_ENERGY_KWH,
    CONF_DIMMER,
    CONF_DISCOVERY,
    CONF_EMETER_PARAMS,
    CONF_LIGHT,
    CONF_MODEL,
    CONF_STRIP,
    CONF_SW_VERSION,
    CONF_SWITCH,
    COORDINATORS,
    PLATFORMS,
    UNAVAILABLE_DEVICES,
    UNAVAILABLE_RETRY_DELAY,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "tplink"

TPLINK_HOST_SCHEMA = vol.Schema({vol.Required(CONF_HOST): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_LIGHT, default=[]): vol.All(
                    cv.ensure_list, [TPLINK_HOST_SCHEMA]
                ),
                vol.Optional(CONF_SWITCH, default=[]): vol.All(
                    cv.ensure_list, [TPLINK_HOST_SCHEMA]
                ),
                vol.Optional(CONF_STRIP, default=[]): vol.All(
                    cv.ensure_list, [TPLINK_HOST_SCHEMA]
                ),
                vol.Optional(CONF_DIMMER, default=[]): vol.All(
                    cv.ensure_list, [TPLINK_HOST_SCHEMA]
                ),
                vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TP-Link component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][ATTR_CONFIG] = conf

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TPLink from a config entry."""
    config_data = hass.data[DOMAIN].get(ATTR_CONFIG)
    if config_data is None and entry.data:
        config_data = entry.data
    elif config_data is not None:
        hass.config_entries.async_update_entry(entry, data=config_data)

    device_registry = dr.async_get(hass)
    tplink_devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    device_count = len(tplink_devices)
    hass_data: dict[str, Any] = hass.data[DOMAIN]

    # These will contain the initialized devices
    hass_data[CONF_LIGHT] = []
    hass_data[CONF_SWITCH] = []
    hass_data[UNAVAILABLE_DEVICES] = []
    lights: list[SmartDevice] = hass_data[CONF_LIGHT]
    switches: list[SmartPlug] = hass_data[CONF_SWITCH]
    unavailable_devices: list[SmartDevice] = hass_data[UNAVAILABLE_DEVICES]

    # Add static devices
    static_devices = SmartDevices()
    if config_data is not None:
        static_devices = get_static_devices(config_data)

        lights.extend(static_devices.lights)
        switches.extend(static_devices.switches)

    # Add discovered devices
    if config_data is None or config_data[CONF_DISCOVERY]:
        discovered_devices = await async_discover_devices(
            hass, static_devices, device_count
        )

        lights.extend(discovered_devices.lights)
        switches.extend(discovered_devices.switches)

    if lights:
        _LOGGER.debug(
            "Got %s lights: %s", len(lights), ", ".join(d.host for d in lights)
        )

    if switches:
        _LOGGER.debug(
            "Got %s switches: %s",
            len(switches),
            ", ".join(d.host for d in switches),
        )

    async def async_retry_devices(self) -> None:
        """Retry unavailable devices."""
        unavailable_devices: list[SmartDevice] = hass_data[UNAVAILABLE_DEVICES]
        _LOGGER.debug(
            "retry during setup unavailable devices: %s",
            [d.host for d in unavailable_devices],
        )

        for device in unavailable_devices:
            try:
                device.get_sysinfo()
            except SmartDeviceException:
                continue
            _LOGGER.debug(
                "at least one device is available again, so reload integration"
            )
            await hass.config_entries.async_reload(entry.entry_id)
            break

    # prepare DataUpdateCoordinators
    hass_data[COORDINATORS] = {}
    for switch in switches:

        try:
            await hass.async_add_executor_job(switch.get_sysinfo)
        except SmartDeviceException:
            _LOGGER.warning(
                "Device at '%s' not reachable during setup, will retry later",
                switch.host,
            )
            unavailable_devices.append(switch)
            continue

        hass_data[COORDINATORS][
            switch.context or switch.mac
        ] = coordinator = SmartPlugDataUpdateCoordinator(hass, switch)
        await coordinator.async_config_entry_first_refresh()

    if unavailable_devices:
        entry.async_on_unload(
            async_track_time_interval(
                hass, async_retry_devices, UNAVAILABLE_RETRY_DELAY
            )
        )
        unavailable_devices_hosts = [d.host for d in unavailable_devices]
        hass_data[CONF_SWITCH] = [
            s for s in switches if s.host not in unavailable_devices_hosts
        ]

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass_data: dict[str, Any] = hass.data[DOMAIN]
    if unload_ok:
        hass_data.clear()

    return unload_ok


class SmartPlugDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for specific SmartPlug."""

    def __init__(
        self,
        hass: HomeAssistant,
        smartplug: SmartPlug,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific SmartPlug."""
        self.smartplug = smartplug

        update_interval = timedelta(seconds=30)
        super().__init__(
            hass, _LOGGER, name=smartplug.alias, update_interval=update_interval
        )

    async def _async_update_data(self) -> dict:
        """Fetch all device and sensor data from api."""
        try:
            info = self.smartplug.sys_info
            data = {
                CONF_HOST: self.smartplug.host,
                CONF_MAC: info["mac"],
                CONF_MODEL: info["model"],
                CONF_SW_VERSION: info["sw_ver"],
            }
            if self.smartplug.context is None:
                data[CONF_ALIAS] = info["alias"]
                data[CONF_DEVICE_ID] = info["mac"]
                data[CONF_STATE] = (
                    self.smartplug.state == self.smartplug.SWITCH_STATE_ON
                )
            else:
                plug_from_context = next(
                    c
                    for c in self.smartplug.sys_info["children"]
                    if c["id"] == self.smartplug.context
                )
                data[CONF_ALIAS] = plug_from_context["alias"]
                data[CONF_DEVICE_ID] = self.smartplug.context
                data[CONF_STATE] = plug_from_context["state"] == 1
            if self.smartplug.has_emeter:
                emeter_readings = self.smartplug.get_emeter_realtime()
                data[CONF_EMETER_PARAMS] = {
                    ATTR_CURRENT_POWER_W: round(float(emeter_readings["power"]), 2),
                    ATTR_TOTAL_ENERGY_KWH: round(float(emeter_readings["total"]), 3),
                    ATTR_VOLTAGE: round(float(emeter_readings["voltage"]), 1),
                    ATTR_CURRENT_A: round(float(emeter_readings["current"]), 2),
                    ATTR_LAST_RESET: {ATTR_TOTAL_ENERGY_KWH: utc_from_timestamp(0)},
                }
                emeter_statics = self.smartplug.get_emeter_daily()
                data[CONF_EMETER_PARAMS][ATTR_LAST_RESET][
                    ATTR_TODAY_ENERGY_KWH
                ] = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                if emeter_statics.get(int(time.strftime("%e"))):
                    data[CONF_EMETER_PARAMS][ATTR_TODAY_ENERGY_KWH] = round(
                        float(emeter_statics[int(time.strftime("%e"))]), 3
                    )
                else:
                    # today's consumption not available, when device was off all the day
                    data[CONF_EMETER_PARAMS][ATTR_TODAY_ENERGY_KWH] = 0.0
        except SmartDeviceException as ex:
            raise UpdateFailed(ex) from ex

        self.name = data[CONF_ALIAS]
        return data
