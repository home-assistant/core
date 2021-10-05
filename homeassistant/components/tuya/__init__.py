"""Support for Tuya Smart devices."""

import itertools
import logging

from tuya_iot import (
    AuthType,
    TuyaDevice,
    TuyaDeviceListener,
    TuyaDeviceManager,
    TuyaHomeManager,
    TuyaOpenAPI,
    TuyaOpenMQ,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_AUTH_TYPE,
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT,
    CONF_PASSWORD,
    CONF_PROJECT_TYPE,
    CONF_USERNAME,
    DOMAIN,
    PLATFORMS,
    TUYA_DEVICE_MANAGER,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_DEVICES,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
    TUYA_HA_TUYA_MAP,
    TUYA_HOME_MANAGER,
    TUYA_MQTT_LISTENER,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup hass config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        TUYA_HA_TUYA_MAP: {},
        TUYA_HA_DEVICES: set(),
    }

    # Project type has been renamed to auth type in the upstream Tuya IoT SDK.
    # This migrates existing config entries to reflect that name change.
    if CONF_PROJECT_TYPE in entry.data:
        data = {**entry.data, CONF_AUTH_TYPE: entry.data[CONF_PROJECT_TYPE]}
        data.pop(CONF_PROJECT_TYPE)
        hass.config_entries.async_update_entry(entry, data=data)

    success = await _init_tuya_sdk(hass, entry)

    if not success:
        hass.data[DOMAIN].pop(entry.entry_id)

        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return bool(success)


async def _init_tuya_sdk(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    auth_type = AuthType(entry.data[CONF_AUTH_TYPE])
    api = TuyaOpenAPI(
        endpoint=entry.data[CONF_ENDPOINT],
        access_id=entry.data[CONF_ACCESS_ID],
        access_secret=entry.data[CONF_ACCESS_SECRET],
        auth_type=auth_type,
    )

    api.set_dev_channel("hass")

    if auth_type == AuthType.CUSTOM:
        response = await hass.async_add_executor_job(
            api.connect, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )
    else:
        response = await hass.async_add_executor_job(
            api.connect,
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
    hass.data[DOMAIN][entry.entry_id][TUYA_HOME_MANAGER] = home_manager

    listener = DeviceListener(hass, entry)
    hass.data[DOMAIN][entry.entry_id][TUYA_MQTT_LISTENER] = listener
    device_manager.add_device_listener(listener)
    hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER] = device_manager

    # Clean up device entities
    await cleanup_device_registry(hass, entry)

    _LOGGER.debug("init support type->%s", PLATFORMS)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def cleanup_device_registry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""

    device_registry_object = device_registry.async_get(hass)
    device_manager = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER]

    for dev_id, device_entry in list(device_registry_object.devices.items()):
        for item in device_entry.identifiers:
            if DOMAIN == item[0] and item[1] not in device_manager.device_map:
                device_registry_object.async_remove_device(dev_id)
                break


@callback
def async_remove_hass_device(hass: HomeAssistant, device_id: str) -> None:
    """Remove device from hass cache."""
    device_registry_object = device_registry.async_get(hass)
    for device_entry in list(device_registry_object.devices.values()):
        if device_id in list(device_entry.identifiers)[0]:
            device_registry_object.async_remove_device(device_entry.id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the Tuya platforms."""
    _LOGGER.debug("integration unload")
    unload = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload:
        device_manager = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER]
        device_manager.mq.stop()
        device_manager.remove_device_listener(
            hass.data[DOMAIN][entry.entry_id][TUYA_MQTT_LISTENER]
        )

        hass.data[DOMAIN].pop(entry.entry_id)

        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload


class DeviceListener(TuyaDeviceListener):
    """Device Update Listener."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Init DeviceListener."""

        self.hass = hass
        self.entry = entry

    def update_device(self, device: TuyaDevice) -> None:
        """Update device status."""
        if device.id in self.hass.data[DOMAIN][self.entry.entry_id][TUYA_HA_DEVICES]:
            _LOGGER.debug(
                "_update-->%s;->>%s",
                self,
                device.id,
            )
            dispatcher_send(self.hass, f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{device.id}")

    def add_device(self, device: TuyaDevice) -> None:
        """Add device added listener."""
        device_add = False

        if device.category in itertools.chain(
            *self.hass.data[DOMAIN][self.entry.entry_id][TUYA_HA_TUYA_MAP].values()
        ):
            ha_tuya_map = self.hass.data[DOMAIN][self.entry.entry_id][TUYA_HA_TUYA_MAP]
            self.hass.add_job(async_remove_hass_device, self.hass, device.id)

            for domain, tuya_list in ha_tuya_map.items():
                if device.category in tuya_list:
                    device_add = True
                    _LOGGER.debug(
                        "Add device category->%s; domain-> %s",
                        device.category,
                        domain,
                    )
                    self.hass.data[DOMAIN][self.entry.entry_id][TUYA_HA_DEVICES].add(
                        device.id
                    )
                    dispatcher_send(
                        self.hass, TUYA_DISCOVERY_NEW.format(domain), [device.id]
                    )

        if device_add:
            device_manager = self.hass.data[DOMAIN][self.entry.entry_id][
                TUYA_DEVICE_MANAGER
            ]
            device_manager.mq.stop()
            tuya_mq = TuyaOpenMQ(device_manager.api)
            tuya_mq.start()

            device_manager.mq = tuya_mq
            tuya_mq.add_message_listener(device_manager.on_message)

    def remove_device(self, device_id: str) -> None:
        """Add device removed listener."""
        _LOGGER.debug("tuya remove device:%s", device_id)
        self.hass.add_job(async_remove_hass_device, self.hass, device_id)
