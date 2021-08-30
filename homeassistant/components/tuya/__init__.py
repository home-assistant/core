#!/usr/bin/env python3
"""Support for Tuya Smart devices."""

import itertools
import logging

from tuya_iot import (
    ProjectType,
    TuyaDevice,
    TuyaDeviceListener,
    TuyaDeviceManager,
    TuyaHomeManager,
    TuyaOpenAPI,
    TuyaOpenMQ,
    tuya_logger,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT,
    CONF_PASSWORD,
    CONF_PROJECT_TYPE,
    CONF_USERNAME,
    DOMAIN,
    TUYA_DEVICE_MANAGER,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_DEVICES,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
    TUYA_HA_TUYA_MAP,
    TUYA_HOME_MANAGER,
    TUYA_MQTT_LISTENER,
    TUYA_SUPPORT_HA_TYPE,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_PROJECT_TYPE): int,
                    vol.Required(CONF_ENDPOINT): cv.string,
                    vol.Required(CONF_ACCESS_ID): cv.string,
                    vol.Required(CONF_ACCESS_SECRET): cv.string,
                    CONF_USERNAME: cv.string,
                    CONF_PASSWORD: cv.string,
                    CONF_COUNTRY_CODE: cv.string,
                    CONF_APP_TYPE: cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)

# decrypt or encrypt entry info


async def _init_tuya_sdk(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # decrypt or encrypt entry info
    project_type = ProjectType(entry.data[CONF_PROJECT_TYPE])
    api = TuyaOpenAPI(
        entry.data[CONF_ENDPOINT],
        entry.data[CONF_ACCESS_ID],
        entry.data[CONF_ACCESS_SECRET],
        project_type,
    )

    api.set_dev_channel("hass")

    if project_type == ProjectType.INDUSTY_SOLUTIONS:
        response = await hass.async_add_executor_job(
            api.login, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )
    else:
        response = await hass.async_add_executor_job(
            api.login,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_COUNTRY_CODE],
            entry.data[CONF_APP_TYPE],
        )

    if response.get("success", False) is False:
        _LOGGER.error("Tuya login error response: %s", response)
        return False

    tuya_mq = TuyaOpenMQ(api)
    tuya_mq.start()

    device_manager = TuyaDeviceManager(api, tuya_mq)

    # Get device list
    home_manager = TuyaHomeManager(api, tuya_mq, device_manager)
    await hass.async_add_executor_job(home_manager.update_device_cache)
    hass.data[DOMAIN][TUYA_HOME_MANAGER] = home_manager

    listener = DeviceListener(hass)
    hass.data[DOMAIN][TUYA_MQTT_LISTENER] = listener
    device_manager.add_device_listener(listener)
    hass.data[DOMAIN][TUYA_DEVICE_MANAGER] = device_manager

    # Clean up device entities
    await cleanup_device_registry(hass)

    _LOGGER.debug("init support type->%s", TUYA_SUPPORT_HA_TYPE)

    for platform in TUYA_SUPPORT_HA_TYPE:
        _LOGGER.debug("tuya async platform-->%s", platform)
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def cleanup_device_registry(hass: HomeAssistant) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""

    __device_registry = device_registry.async_get(hass)
    device_manager = hass.data[DOMAIN][TUYA_DEVICE_MANAGER]

    for dev_id, device_entity in list(__device_registry.devices.items()):
        for item in device_entity.identifiers:
            if DOMAIN == item[0] and item[1] not in device_manager.device_map:
                __device_registry.async_remove_device(dev_id)
                break


@callback
def async_remove_hass_device(hass: HomeAssistant, device_id: str) -> None:
    """Remove device from hass cache."""
    __device_registry = device_registry.async_get(hass)
    for entity in list(__device_registry.devices.values()):
        if device_id in list(entity.identifiers)[0]:
            __device_registry.async_remove_device(entity.id)


async def async_setup(hass, config):
    """Set up the Tuya integration."""
    tuya_logger.setLevel(_LOGGER.level)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the Tuya platforms."""
    _LOGGER.debug("integration unload")
    unload = await hass.config_entries.async_unload_platforms(
        entry, TUYA_SUPPORT_HA_TYPE
    )
    if unload:
        __device_manager = hass.data[DOMAIN][TUYA_DEVICE_MANAGER]
        __device_manager.mq.stop()
        __device_manager.remove_device_listener(hass.data[DOMAIN][TUYA_MQTT_LISTENER])

        hass.data.pop(DOMAIN)

    return unload


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup hass config entry."""
    _LOGGER.debug("tuya.__init__.async_setup_entry-->%s", entry.data)

    hass.data[DOMAIN] = {TUYA_HA_TUYA_MAP: {}, TUYA_HA_DEVICES: {}}

    success = await _init_tuya_sdk(hass, entry)
    if not success:
        return False

    return True


class DeviceListener(TuyaDeviceListener):
    """Device Update Listener."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Init DeviceListener."""

        self.hass = hass

    def update_device(self, device: TuyaDevice) -> None:
        """Update device status."""
        if device.id in self.hass.data[DOMAIN][TUYA_HA_DEVICES]:
            _LOGGER.debug(
                "_update-->%s;->>%s",
                self,
                self.hass.data[DOMAIN][TUYA_HA_DEVICES][device.id].tuya_device.status,
            )
            async_dispatcher_send(self.hass, TUYA_HA_SIGNAL_UPDATE_ENTITY)

    def add_device(self, device: TuyaDevice) -> None:
        """Add device added listener."""
        device_add = False

        _LOGGER.debug(
            """add device category->%s; keys->,
            {hass.data[DOMAIN][TUYA_HA_TUYA_MAP].keys()}""",
            device.category,
        )

        if device.category in itertools.chain(
            *self.hass.data[DOMAIN][TUYA_HA_TUYA_MAP].values()
        ):
            ha_tuya_map = self.hass.data[DOMAIN][TUYA_HA_TUYA_MAP]

            self.hass.add_job(async_remove_hass_device, self.hass, device.id)

            for key, tuya_list in ha_tuya_map.items():
                if device.category in tuya_list:
                    device_add = True
                    dispatcher_send(
                        self.hass, TUYA_DISCOVERY_NEW.format(key), [device.id]
                    )

        if device_add:
            device_manager = self.hass.data[DOMAIN][TUYA_DEVICE_MANAGER]
            device_manager.mq.stop()
            tuya_mq = TuyaOpenMQ(device_manager.api)
            tuya_mq.start()

            device_manager.mq = tuya_mq
            tuya_mq.add_message_listener(device_manager.on_message)

    def remove_device(self, device_id: str) -> None:
        """Add device removed listener."""
        _LOGGER.debug("tuya remove device:%s", device_id)
        self.hass.add_job(async_remove_hass_device, self.hass, device_id)
