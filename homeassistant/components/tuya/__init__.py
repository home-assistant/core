"""Support for Tuya Smart devices."""
from __future__ import annotations

from typing import Any, NamedTuple

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
from tuya_sharing import (
    CustomerDevice,
    Manager,
    SharingDeviceListener,
    SharingTokenListener,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_AUTH_TYPE,
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT,
    CONF_PASSWORD,
    CONF_TERMINAL_INFO,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    CONF_USERNAME,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    TUYA_CLIENT_ID,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
    TUYA_SMART_APP,
)


class HomeAssistantTuyaData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    device_listener: LegacyDeviceListener | DeviceListener
    device_manager: TuyaDeviceManager | Manager
    manager: TuyaHomeManager | Manager


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup hass config entry."""
    hass.data.setdefault(DOMAIN, {})

    # If the config entry has an app type, it indicates an old config entry
    # in case it is using the Tuya Smart app, we have no migration path.
    # In that case, we keep everything working for now, and raise a repair.
    if CONF_APP_TYPE in entry.data:
        if entry.data[CONF_APP_TYPE] == TUYA_SMART_APP:
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
                        api.connect,
                        entry.data[CONF_USERNAME],
                        entry.data[CONF_PASSWORD],
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
            listener = LegacyDeviceListener(hass, device_manager, device_ids)
            device_manager.add_device_listener(listener)

            tuya = HomeAssistantTuyaData(
                device_listener=listener,
                device_manager=device_manager,
                manager=home_manager,
            )
        else:
            # Smart Life app, we can migrate these. Let's trigger a reauth.
            pass

    else:
        # New style handling
        token_listener = TokenListener(hass, entry)
        manager = Manager(
            TUYA_CLIENT_ID,
            entry.data[CONF_USER_CODE],
            entry.data[CONF_TERMINAL_INFO],
            entry.data[CONF_ENDPOINT],
            entry.data[CONF_TOKEN_INFO],
            token_listener,
        )

        listener = DeviceListener(hass, manager)
        manager.add_device_listener(listener)
        tuya = HomeAssistantTuyaData(
            device_manager=manager,
            device_listener=listener,
            manager=manager,
        )

        await hass.async_add_executor_job(tuya.manager.refresh_mq)

    hass.data[DOMAIN][entry.entry_id] = tuya

    # Get devices & clean up device entities
    await hass.async_add_executor_job(tuya.manager.update_device_cache)
    await cleanup_device_registry(hass, tuya.device_manager)

    # Register known device IDs
    device_registry = dr.async_get(hass)
    for device in tuya.device_manager.device_map.values():
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
    hass: HomeAssistant, device_manager: TuyaDeviceManager | Manager
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


class LegacyDeviceListener(TuyaDeviceListener):
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


class DeviceListener(SharingDeviceListener):
    """Device Update Listener."""

    def __init__(
        self,
        hass: HomeAssistant,
        manager: Manager,
    ) -> None:
        """Init DeviceListener."""
        self.hass = hass
        self.manager = manager

    def update_device(self, device: CustomerDevice) -> None:
        """Update device status."""
        LOGGER.debug(
            "Received update for device %s: %s",
            device.id,
            self.manager.device_map[device.id].status,
        )
        dispatcher_send(self.hass, f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{device.id}")

    def add_device(self, device: CustomerDevice) -> None:
        """Add device added listener."""
        # Ensure the device isn't present stale
        self.hass.add_job(self.async_remove_device, device.id)

        dispatcher_send(self.hass, TUYA_DISCOVERY_NEW, [device.id])

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


class TokenListener(SharingTokenListener):
    """Token Update Listener."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Init TokenListener."""
        self.hass = hass
        self.entry = entry

    def update_token(self, token_info: dict[str, Any]) -> None:
        """Update token info in the config entry."""
        data = {**self.entry.data, CONF_TOKEN_INFO: token_info}
        self.hass.config_entries.async_update_entry(self.entry, data=data)
