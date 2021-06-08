#!/usr/bin/env python3
"""Support for Tuya Smart devices."""

import itertools
import logging
from typing import Any

from tuya_iot import (
    ProjectType,
    TuyaDevice,
    TuyaDeviceListener,
    TuyaDeviceManager,
    TuyaHomeManager,
    TuyaOpenAPI,
    TuyaOpenMQ,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

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
    TUYA_HA_TUYA_MAP,
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

first_init = True


async def _init_tuya_sdk(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry_data = entry.data
    project_type = ProjectType(entry_data[CONF_PROJECT_TYPE])
    api = TuyaOpenAPI(
        entry_data[CONF_ENDPOINT],
        entry_data[CONF_ACCESS_ID],
        entry_data[CONF_ACCESS_SECRET],
        project_type,
    )

    api.set_dev_channel("hass")

    response = (
        await hass.async_add_executor_job(
            api.login, entry_data[CONF_USERNAME], entry_data[CONF_PASSWORD]
        )
        if project_type == ProjectType.INDUSTY_SOLUTIONS
        else await hass.async_add_executor_job(
            api.login,
            entry_data[CONF_USERNAME],
            entry_data[CONF_PASSWORD],
            entry_data[CONF_COUNTRY_CODE],
            entry_data[CONF_APP_TYPE],
        )
    )
    if response.get("success", False) is False:
        _LOGGER.error(
            "Tuya login error response: %s",
            response,
        )
        return False

    mq = TuyaOpenMQ(api)
    mq.start()

    deviceManager = TuyaDeviceManager(api, mq)

    # Get device list
    home_manager = TuyaHomeManager(api, mq, deviceManager)
    await hass.async_add_executor_job(home_manager.updateDeviceCache)

    class tuyaDeviceListener(TuyaDeviceListener):
        def updateDevice(self, device: TuyaDevice):
            for haDevice in hass.data[DOMAIN][TUYA_HA_DEVICES]:
                if haDevice.tuyaDevice.id == device.id:
                    print("_update-->", self, ";->>", haDevice.tuyaDevice.status)
                    haDevice.schedule_update_ha_state()

        def addDevice(self, device: TuyaDevice):
            print("tuya device add-->", device)

            device_add = False

            print(
                "add device category->",
                device.category,
                "; keys->",
                hass.data[DOMAIN][TUYA_HA_TUYA_MAP].keys(),
            )
            if device.category in itertools.chain(
                *hass.data[DOMAIN][TUYA_HA_TUYA_MAP].values()
            ):
                map = hass.data[DOMAIN][TUYA_HA_TUYA_MAP]

                remove_device(hass, device.id)

                for key, list in map.items():
                    print("add device key->", key, "; value->", list)
                    if device.category in list:
                        device_add = True
                        async_dispatcher_send(
                            hass, TUYA_DISCOVERY_NEW.format(key), [device.id]
                        )

            if device_add:
                device_manager = hass.data[DOMAIN][TUYA_DEVICE_MANAGER]
                device_manager.mq.stop()
                mq = TuyaOpenMQ(device_manager.api)
                mq.start()
                hass.data[DOMAIN][TUYA_DEVICE_MANAGER].mq = mq

        def removeDevice(self, id: str):
            print("tuya remove device:", id)
            remove_device(hass, id)

    __listener = tuyaDeviceListener()
    hass.data[DOMAIN][TUYA_MQTT_LISTENER] = __listener
    deviceManager.addDeviceListener(__listener)
    hass.data[DOMAIN][TUYA_DEVICE_MANAGER] = deviceManager

    # Clean up device entities
    await cleanup_device_registry(hass)

    print("domain key->", str(hass.data[DOMAIN][TUYA_HA_TUYA_MAP]))
    print("init support type->", TUYA_SUPPORT_HA_TYPE)

    global first_init

    if first_init:
        for platform in TUYA_SUPPORT_HA_TYPE:
            print("tuya async platform-->", platform)
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )
        first_init = False
    else:
        for device_id, device in deviceManager.deviceMap.items():
            for ha_type, map in hass.data[DOMAIN][TUYA_HA_TUYA_MAP].items():
                if device.category in map:
                    async_dispatcher_send(
                        hass, TUYA_DISCOVERY_NEW.format(ha_type), [device_id]
                    )

    return True


async def cleanup_device_registry(hass: HomeAssistant):
    """Remove device registry entry if there are no remaining entities."""

    device_registry = hass.helpers.device_registry.async_get(hass)

    orphan = set(device_registry.devices)

    for dev_id in orphan:
        device_registry.async_remove_device(dev_id)


def remove_device(hass: HomeAssistant, device_id: str):
    """Remove device from hass cache."""
    device_registry = hass.helpers.device_registry.async_get(hass)
    entity_registry = hass.helpers.entity_registry.async_get(hass)
    for entity in list(entity_registry.entities.values()):
        if entity.unique_id.startswith(device_id):
            entity_registry.async_remove(entity.entity_id)
            if device_registry.async_get(entity.device_id):
                device_registry.async_remove_device(entity.device_id)


async def async_setup(hass, config):
    """Set up the Tuya integration."""

    conf = config.get(DOMAIN)

    print("Tuya async setup conf %s \n" % conf)
    if conf is not None:

        async def flow_init() -> Any:
            try:
                result = await hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
                )
            except Exception as inst:
                print(inst.args)
            print("Tuya async setup flow_init")
            return result

        hass.async_create_task(flow_init())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unloading the Tuya platforms."""
    # TODO handle tuya integration unload
    # domain_data = hass.data[DOMAIN]
    print("integration unload")
    __device_manager = hass.data[DOMAIN][TUYA_DEVICE_MANAGER]
    __device_manager.mq.stop()
    __device_manager.removeDeviceListener(hass.data[DOMAIN][TUYA_MQTT_LISTENER])
    hass.data[DOMAIN][TUYA_MQTT_LISTENER] = None
    hass.data[DOMAIN][TUYA_DEVICE_MANAGER] = None

    hass.data[DOMAIN][TUYA_HA_DEVICES] = []

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Async setup hass config entry."""
    print("tuya.__init__.async_setup_entry-->", entry.data)

    if first_init:
        hass.data[DOMAIN] = {TUYA_HA_TUYA_MAP: {}, TUYA_HA_DEVICES: []}

    success = await _init_tuya_sdk(hass, entry)
    if not success:
        return False

    return True
