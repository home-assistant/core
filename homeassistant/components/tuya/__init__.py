"""Support for Tuya Smart devices."""
from __future__ import annotations

from typing import NamedTuple

import requests
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
from homeassistant.const import CONF_COUNTRY_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_AUTH_TYPE,
    CONF_ENDPOINT,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
)


class HomeAssistantTuyaData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    device_listener: TuyaDeviceListener
    device_manager: TuyaDeviceManager
    home_manager: TuyaHomeManager


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup hass config entry."""
    hass.data.setdefault(DOMAIN, {})

    auth_type = AuthType(entry.data[CONF_AUTH_TYPE])
    api = TuyaOpenAPI(
        endpoint=entry.data[CONF_ENDPOINT],
        access_id=entry.data[CONF_ACCESS_ID],
        access_secret=entry.data[CONF_ACCESS_SECRET],
        auth_type=auth_type,
    )

    api.set_dev_channel("hass")

    try:
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
    except requests.exceptions.RequestException as err:
        raise ConfigEntryNotReady(err) from err

    if response.get("success", False) is False:
        raise ConfigEntryNotReady(response)

    tuya_mq = TuyaOpenMQ(api)
    tuya_mq.start()

    device_ids: set[str] = set()
    device_manager = TuyaDeviceManager(api, tuya_mq)
    home_manager = TuyaHomeManager(api, tuya_mq, device_manager)
    listener = DeviceListener(hass, device_manager, device_ids)
    device_manager.add_device_listener(listener)

    hass.data[DOMAIN][entry.entry_id] = HomeAssistantTuyaData(
        device_listener=listener,
        device_manager=device_manager,
        home_manager=home_manager,
    )

    # Get devices & clean up device entities
    await hass.async_add_executor_job(home_manager.update_device_cache)
    await cleanup_device_registry(hass, device_manager)

    # Register known device IDs
    device_registry = dr.async_get(hass)
    for device in device_manager.device_map.values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device.id)},
            manufacturer="Tuya",
            name=device.name,
            model=f"{device.product_name} (unsupported)",
        )
        device_ids.add(device.id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def cleanup_device_registry(
    hass: HomeAssistant, device_manager: TuyaDeviceManager
) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""
    device_registry = dr.async_get(hass)
    for dev_id, device_entry in list(device_registry.devices.items()):
        for item in device_entry.identifiers:
            if item[0] == DOMAIN and item[1] not in device_manager.device_map:
                device_registry.async_remove_device(dev_id)
                break


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the Tuya platforms."""
    unload = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload:
        hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]
        hass_data.device_manager.mq.stop()
        hass_data.device_manager.remove_device_listener(hass_data.device_listener)

        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload


class DeviceListener(TuyaDeviceListener):
    """Device Update Listener."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_manager: TuyaDeviceManager,
        device_ids: set[str],
    ) -> None:
        """Init DeviceListener."""
        self.hass = hass
        self.device_manager = device_manager
        self.device_ids = device_ids

    def update_device(self, device: TuyaDevice) -> None:
        """Update device status."""
        if device.id in self.device_ids:
            LOGGER.debug(
                "Received update for device %s: %s",
                device.id,
                self.device_manager.device_map[device.id].status,
            )
            dispatcher_send(self.hass, f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{device.id}")

    def add_device(self, device: TuyaDevice) -> None:
        """Add device added listener."""
        # Ensure the device isn't present stale
        self.hass.add_job(self.async_remove_device, device.id)

        self.device_ids.add(device.id)
        dispatcher_send(self.hass, TUYA_DISCOVERY_NEW, [device.id])

        device_manager = self.device_manager
        device_manager.mq.stop()
        tuya_mq = TuyaOpenMQ(device_manager.api)
        tuya_mq.start()

        device_manager.mq = tuya_mq
        tuya_mq.add_message_listener(device_manager.on_message)

    def remove_device(self, device_id: str) -> None:
        """Add device removed listener."""
        self.hass.add_job(self.async_remove_device, device_id)

    @callback
    def async_remove_device(self, device_id: str) -> None:
        """Remove device from Home Assistant."""
        LOGGER.debug("Remove device: %s", device_id)
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, device_id)}
        )
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)
            self.device_ids.discard(device_id)
