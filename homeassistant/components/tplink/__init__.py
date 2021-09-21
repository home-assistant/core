"""Component to embed TP-Link smart home devices."""
from __future__ import annotations

from datetime import timedelta
import logging
import time
from typing import Any

from kasa import SmartDevice, SmartDeviceException, SmartPlug, SmartStrip
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.switch import ATTR_CURRENT_POWER_W, ATTR_TODAY_ENERGY_KWH
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_VOLTAGE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .common import SmartDevices, async_discover_devices, get_static_devices
from .const import (
    ATTR_CONFIG,
    ATTR_CURRENT_A,
    ATTR_TOTAL_ENERGY_KWH,
    CONF_DIMMER,
    CONF_DISCOVERY,
    CONF_EMETER_PARAMS,
    CONF_LIGHT,
    CONF_STRIP,
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
    switches: list[SmartPlug | SmartStrip] = hass_data[CONF_SWITCH]
    unavailable_devices: list[SmartDevice] = hass_data[UNAVAILABLE_DEVICES]

    # Add static devices
    static_devices = SmartDevices()
    if config_data is not None:
        static_devices = await get_static_devices(config_data)

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
                await device.update()
            except SmartDeviceException:
                continue
            _LOGGER.debug(
                "at least one device is available again, so reload integration"
            )
            await hass.config_entries.async_reload(entry.entry_id)
            break

    # prepare DataUpdateCoordinators
    hass_data[COORDINATORS]: dict[str, TPLinkDataUpdateCoordinator] = {}
    for dev in switches + lights:
        try:
            _ = await dev.update()
        except SmartDeviceException:
            _LOGGER.warning(
                "Device at '%s' not reachable during setup, will retry later",
                dev.host,
            )
            unavailable_devices.append(dev)
            continue

        hass_data[COORDINATORS][
            dev.device_id
        ] = coordinator = TPLinkDataUpdateCoordinator(hass, dev)
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


class TPLinkDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for specific SmartPlug."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: SmartDevice,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific SmartPlug."""
        self.device = device

        update_interval = timedelta(seconds=30)
        super().__init__(
            hass,
            _LOGGER,
            name=device.alias,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict:
        """Fetch all device and sensor data from api."""
        try:
            await self.device.update()
            data = {}

            # Check if the device has emeter
            if self.device.has_emeter:
                emeter_readings = self.device.emeter_realtime
                data[CONF_EMETER_PARAMS] = {
                    # Power is always available, also on bulbs
                    ATTR_CURRENT_POWER_W: emeter_readings["power"],
                    ATTR_TOTAL_ENERGY_KWH: emeter_readings.get("total", None),
                    ATTR_VOLTAGE: emeter_readings.get("voltage", None),
                    ATTR_CURRENT_A: emeter_readings.get("current", None),
                }
                # TODO: check if the property getter can be used here
                emeter_statics = await self.device.get_emeter_daily()
                if emeter_statics.get(int(time.strftime("%e"))):
                    data[CONF_EMETER_PARAMS][ATTR_TODAY_ENERGY_KWH] = round(
                        float(emeter_statics[int(time.strftime("%e"))]), 3
                    )
                else:
                    # today's consumption not available, when device was off all the day
                    # bulb's do not report this information, so filter it out
                    consumption_today = 0.0
                    if self.device.is_bulb:
                        consumption_today = None
                    data[CONF_EMETER_PARAMS][ATTR_TODAY_ENERGY_KWH] = consumption_today
        except SmartDeviceException as ex:
            raise UpdateFailed(ex) from ex

        self.name = self.device.alias
        return data
