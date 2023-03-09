"""VeSync integration."""
import logging
from typing import Any

from pyvesync import VeSync

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .common import DEVICE_HELPER
from .const import (
    DOMAIN,
    SERVICE_UPDATE_DEVS,
    VS_BINARY_SENSORS,
    VS_DISCOVERY,
    VS_FANS,
    VS_HUMIDIFIERS,
    VS_LIGHTS,
    VS_MANAGER,
    VS_NUMBERS,
    VS_SENSORS,
    VS_SWITCHES,
)

PLATFORMS = [
    Platform.SWITCH,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.HUMIDIFIER,
    Platform.NUMBER,
    Platform.BINARY_SENSOR,
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Vesync as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    time_zone = str(hass.config.time_zone)

    manager = VeSync(username, password, time_zone)

    login = await hass.async_add_executor_job(manager.login)

    if not login:
        _LOGGER.error("Unable to login to the VeSync server")
        return False

    device_dict = await _async_process_devices(hass, manager)

    forward_setup = hass.config_entries.async_forward_entry_setup

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_MANAGER] = manager

    switches = hass.data[DOMAIN][VS_SWITCHES] = []
    fans = hass.data[DOMAIN][VS_FANS] = []
    lights = hass.data[DOMAIN][VS_LIGHTS] = []
    sensors = hass.data[DOMAIN][VS_SENSORS] = []
    humidifiers = hass.data[DOMAIN][VS_HUMIDIFIERS] = []
    numbers = hass.data[DOMAIN][VS_NUMBERS] = []
    binary_sensors = hass.data[DOMAIN][VS_BINARY_SENSORS] = []
    platforms = []

    if device_dict[VS_SWITCHES]:
        switches.extend(device_dict[VS_SWITCHES])
        platforms.append(Platform.SWITCH)

    if device_dict[VS_FANS]:
        fans.extend(device_dict[VS_FANS])
        platforms.append(Platform.FAN)

    if device_dict[VS_HUMIDIFIERS]:
        humidifiers.extend(device_dict[VS_HUMIDIFIERS])
        platforms.append(Platform.HUMIDIFIER)

    if device_dict[VS_LIGHTS]:
        lights.extend(device_dict[VS_LIGHTS])
        platforms.append(Platform.LIGHT)

    if device_dict[VS_SENSORS]:
        sensors.extend(device_dict[VS_SENSORS])
        platforms.append(Platform.SENSOR)

    if device_dict[VS_NUMBERS]:
        numbers.extend(device_dict[VS_NUMBERS])
        platforms.append(Platform.NUMBER)

    if device_dict[VS_BINARY_SENSORS]:
        binary_sensors.extend(device_dict[VS_BINARY_SENSORS])
        platforms.append(Platform.BINARY_SENSOR)

    await hass.config_entries.async_forward_entry_setups(config_entry, platforms)

    async def async_new_device_discovery(service: ServiceCall) -> None:
        """Discover if new devices should be added."""
        await _async_new_device_discovery(hass, config_entry, forward_setup, service)

    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_DEVS, async_new_device_discovery
    )

    return True


async def _async_process_devices(
    hass: HomeAssistant, manager: VeSync
) -> dict[str, Any]:
    """Assign devices to proper component."""
    devices: dict[str, Any] = {}
    devices[VS_SWITCHES] = []
    devices[VS_FANS] = []
    devices[VS_LIGHTS] = []
    devices[VS_SENSORS] = []
    devices[VS_HUMIDIFIERS] = []
    devices[VS_NUMBERS] = []
    devices[VS_BINARY_SENSORS] = []

    await hass.async_add_executor_job(manager.update)

    if manager.fans:
        for fan in manager.fans:
            # VeSync classifies humidifiers as fans
            if DEVICE_HELPER.is_humidifier(fan.device_type):
                devices[VS_HUMIDIFIERS].append(fan)
            else:
                devices[VS_FANS].append(fan)
            devices[VS_NUMBERS].append(fan)  # for night light and mist level
            devices[VS_SWITCHES].append(fan)  # for automatic stop and display
            devices[VS_LIGHTS].append(fan)  # for night light
            devices[VS_SENSORS].append(fan)
            devices[VS_BINARY_SENSORS].append(fan)
        _LOGGER.info("%d VeSync fans found", len(devices[VS_FANS]))
        _LOGGER.info("%d VeSync humidifiers found", len(devices[VS_HUMIDIFIERS]))

    if manager.bulbs:
        devices[VS_LIGHTS].extend(manager.bulbs)
        _LOGGER.info("%d VeSync lights found", len(manager.bulbs))

    if manager.outlets:
        devices[VS_SWITCHES].extend(manager.outlets)
        # Expose outlets' voltage, power & energy usage as separate sensors
        devices[VS_SENSORS].extend(manager.outlets)
        _LOGGER.info("%d VeSync outlets found", len(manager.outlets))

    if manager.switches:
        for switch in manager.switches:
            if not switch.is_dimmable():
                devices[VS_SWITCHES].append(switch)
            else:
                devices[VS_LIGHTS].append(switch)
        _LOGGER.info("%d VeSync switches found", len(manager.switches))

    return devices


async def _async_new_device_discovery(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    forward_setup,
    service: ServiceCall,
) -> None:
    """Discover if new devices should be added."""
    manager = hass.data[DOMAIN][VS_MANAGER]
    switches = hass.data[DOMAIN][VS_SWITCHES]
    fans = hass.data[DOMAIN][VS_FANS]
    lights = hass.data[DOMAIN][VS_LIGHTS]
    sensors = hass.data[DOMAIN][VS_SENSORS]
    humidifiers = hass.data[DOMAIN][VS_HUMIDIFIERS]
    numbers = hass.data[DOMAIN][VS_NUMBERS]
    binary_sensors = hass.data[DOMAIN][VS_BINARY_SENSORS]

    dev_dict = await _async_process_devices(hass, manager)
    switch_devs = dev_dict.get(VS_SWITCHES, [])
    fan_devs = dev_dict.get(VS_FANS, [])
    light_devs = dev_dict.get(VS_LIGHTS, [])
    sensor_devs = dev_dict.get(VS_SENSORS, [])
    humidifier_devs = dev_dict.get(VS_HUMIDIFIERS, [])
    number_devs = dev_dict.get(VS_NUMBERS, [])
    binary_sensor_devs = dev_dict.get(VS_BINARY_SENSORS, [])

    switch_set = set(switch_devs)
    new_switches = list(switch_set.difference(switches))
    if new_switches and switches:
        switches.extend(new_switches)
        async_dispatcher_send(hass, VS_DISCOVERY.format(VS_SWITCHES), new_switches)
    elif new_switches and not switches:
        switches.extend(new_switches)
        hass.async_create_task(forward_setup(config_entry, Platform.SWITCH))

    fan_set = set(fan_devs)
    new_fans = list(fan_set.difference(fans))
    if new_fans and fans:
        fans.extend(new_fans)
        async_dispatcher_send(hass, VS_DISCOVERY.format(VS_FANS), new_fans)
    elif new_fans and not fans:
        fans.extend(new_fans)
        hass.async_create_task(forward_setup(config_entry, Platform.FAN))

    light_set = set(light_devs)
    new_lights = list(light_set.difference(lights))
    if new_lights and lights:
        lights.extend(new_lights)
        async_dispatcher_send(hass, VS_DISCOVERY.format(VS_LIGHTS), new_lights)
    elif new_lights and not lights:
        lights.extend(new_lights)
        hass.async_create_task(forward_setup(config_entry, Platform.LIGHT))

    humidifier_set = set(humidifier_devs)
    new_humidifiers = list(humidifier_set.difference(humidifiers))
    if new_humidifiers and humidifiers:
        humidifiers.extend(new_humidifiers)
        async_dispatcher_send(
            hass, VS_DISCOVERY.format(VS_HUMIDIFIERS), new_humidifiers
        )
    elif new_humidifiers and not humidifiers:
        humidifiers.extend(new_humidifiers)
        hass.async_create_task(forward_setup(config_entry, Platform.HUMIDIFIER))

    number_set = set(number_devs)
    new_numbers = list(number_set.difference(numbers))
    if new_numbers and numbers:
        numbers.extend(new_numbers)
        async_dispatcher_send(hass, VS_DISCOVERY.format(VS_NUMBERS), new_numbers)
    elif new_numbers and not numbers:
        numbers.extend(new_numbers)
        hass.async_create_task(forward_setup(config_entry, Platform.NUMBER))

    sensor_set = set(sensor_devs)
    new_sensors = list(sensor_set.difference(sensors))
    if new_sensors and sensors:
        sensors.extend(new_sensors)
        async_dispatcher_send(hass, VS_DISCOVERY.format(VS_SENSORS), new_sensors)
    elif new_sensors and not sensors:
        sensors.extend(new_sensors)
        hass.async_create_task(forward_setup(config_entry, Platform.SENSOR))

    binary_sensor_set = set(binary_sensor_devs)
    new_binary_sensors = list(binary_sensor_set.difference(binary_sensors))
    if new_binary_sensors and binary_sensors:
        binary_sensors.extend(new_binary_sensors)
        async_dispatcher_send(
            hass, VS_DISCOVERY.format(VS_BINARY_SENSORS), new_binary_sensors
        )
    elif new_binary_sensors and not binary_sensors:
        binary_sensors.extend(new_binary_sensors)
        hass.async_create_task(forward_setup(config_entry, Platform.BINARY_SENSOR))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
