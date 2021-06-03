#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Support for Tuya Smart devices."""

import logging

import voluptuous as vol
import json
from urllib.request import urlopen
import time
import itertools

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from typing import Any

from .const import (
    DOMAIN,
    CONF_ENDPOINT,
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_COUNTRY_CODE,
    CONF_PROJECT_TYPE,
    CONF_APP_TYPE,
    TUYA_DEVICE_MANAGER,
    TUYA_HA_TUYA_MAP,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_DEVICES,
    TUYA_SUPPORT_HA_TYPE
)

from . import config_flow

from tuya_iot import (
    TuyaOpenAPI,
    TuyaOpenMQ,
    TuyaDeviceManager,
    TuyaDevice,
    TuyaHomeManager,
    ProjectType,
    TuyaDeviceListener
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
                    CONF_APP_TYPE: cv.string
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def _init_tuya_sdk(hass: HomeAssistant, entry_data: dict) -> TuyaDeviceManager:
    project_type = ProjectType(entry_data[CONF_PROJECT_TYPE])
    api = TuyaOpenAPI(
        entry_data[CONF_ENDPOINT],
        entry_data[CONF_ACCESS_ID],
        entry_data[CONF_ACCESS_SECRET],
        project_type)

    api.set_dev_channel('hass')

    response = await hass.async_add_executor_job(api.login,
                                                 entry_data[CONF_USERNAME],
                                                 entry_data[CONF_PASSWORD]) if project_type == ProjectType.INDUSTY_SOLUTIONS else\
        await hass.async_add_executor_job(api.login,
                                          entry_data[CONF_USERNAME],
                                          entry_data[CONF_PASSWORD],
                                          entry_data[CONF_COUNTRY_CODE],
                                          entry_data[CONF_APP_TYPE])
    if response.get('success', False) == False:
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
                    print("_update-->", haDevice.tuyaDevice.status)
                    haDevice.schedule_update_ha_state()

        def addDevice(self, device: TuyaDevice):
            print("tuya device add-->", device)

            device_add = False

            print('add device category->', device.category, '; keys->', hass.data[DOMAIN][TUYA_HA_TUYA_MAP].keys())
            if device.category in itertools.chain(*hass.data[DOMAIN][TUYA_HA_TUYA_MAP].values()):
                map = hass.data[DOMAIN][TUYA_HA_TUYA_MAP]

                remove_device(hass, device.id)

                for key, list in map.items():
                    print('add device key->', key, '; value->', list)
                    if device.category in list:
                        device_add = True
                        async_dispatcher_send(
                            hass, TUYA_DISCOVERY_NEW.format(key), [device.id])
            
            if device_add:
                device_manager = hass.data[DOMAIN][TUYA_DEVICE_MANAGER]
                device_manager.mq.stop()
                mq = TuyaOpenMQ(device_manager.api)
                mq.start()
                hass.data[DOMAIN][TUYA_DEVICE_MANAGER].mq = mq

        def removeDevice(self, id: str):
            print('tuya remove device:', id)
            remove_device(hass, id)

    deviceManager.addDeviceListener(tuyaDeviceListener())
    hass.data[DOMAIN][TUYA_DEVICE_MANAGER] = deviceManager

    # Clean up devcie entities
    await cleanup_device_registry(hass)

    # Create ha devices
    ha_device_dict = {}
    print("domain key->", str(hass.data[DOMAIN][TUYA_HA_TUYA_MAP]))

    return True


async def cleanup_device_registry(hass: HomeAssistant):
    """Remove device registry entry if there are no remaining entities."""

    device_registry = hass.helpers.device_registry.async_get(hass)

    orphan = set(device_registry.devices)

    for dev_id in orphan:
        device_registry.async_remove_device(dev_id)


def remove_device(hass: HomeAssistant, device_id: str):
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

    print('Tuya async setup conf %s \n' % conf)
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

        hass.async_create_task(
            flow_init()
        )

    # print("Tuya async setup true \n")
    # config_flow.TuyaFlowHandler.async_register_implementation(
    #         hass,
    #         config_entry_oauth2_flow.LocalOAuth2Implementation(
    #             hass,
    #             DOMAIN,
    #             config[DOMAIN][CONF_ACCESS_ID],
    #             config[DOMAIN][CONF_ACCESS_SECRET],
    #             "https://open-platform.fast-cn.wgine.com/login/open/tuya/login/v1/index.html",
    #             config[DOMAIN][CONF_ENDPOINT] + "/v1.0/token",
    #         ),
    #     )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unloading the Tuya platforms."""
    ## TODO handle tuya integration unload
    # domain_data = hass.data[DOMAIN]
    hass.data[DOMAIN][TUYA_DEVICE_MANAGER].mq.stop()

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    print("tuya.__init__.async_setup_entry-->", entry.data)

    hass.data[DOMAIN] = {
        TUYA_HA_TUYA_MAP: {},
        TUYA_HA_DEVICES: []
    }

    success = await _init_tuya_sdk(hass, entry.data)
    # await hass.async_add_executor_job(_init_tuya_sdk, hass, entry.data)
    if not success:
        return False

    print("init support type->", TUYA_SUPPORT_HA_TYPE)
    for platform in TUYA_SUPPORT_HA_TYPE:
        print("tuya async platform-->", platform)
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                entry, platform
            )
        )

    return True
