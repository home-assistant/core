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

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
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
    LOGGER,
    PLATFORMS,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
    DPCode,
)


class HomeAssistantTuyaData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    device_listener: TuyaDeviceListener
    device_manager: TuyaDeviceManager
    home_manager: TuyaHomeManager


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup hass config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Project type has been renamed to auth type in the upstream Tuya IoT SDK.
    # This migrates existing config entries to reflect that name change.
    if CONF_PROJECT_TYPE in entry.data:
        data = {**entry.data, CONF_AUTH_TYPE: entry.data[CONF_PROJECT_TYPE]}
        data.pop(CONF_PROJECT_TYPE)
        hass.config_entries.async_update_entry(entry, data=data)

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

    # Migrate old unique_ids to the new format
    async_migrate_entities_unique_ids(hass, entry, device_manager)

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

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def cleanup_device_registry(
    hass: HomeAssistant, device_manager: TuyaDeviceManager
) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""
    device_registry = dr.async_get(hass)
    for dev_id, device_entry in list(device_registry.devices.items()):
        for item in device_entry.identifiers:
            if DOMAIN == item[0] and item[1] not in device_manager.device_map:
                device_registry.async_remove_device(dev_id)
                break


@callback
def async_migrate_entities_unique_ids(
    hass: HomeAssistant, config_entry: ConfigEntry, device_manager: TuyaDeviceManager
) -> None:
    """Migrate unique_ids in the entity registry to the new format."""
    entity_registry = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    light_entries = {
        entry.unique_id: entry
        for entry in registry_entries
        if entry.domain == LIGHT_DOMAIN
    }
    switch_entries = {
        entry.unique_id: entry
        for entry in registry_entries
        if entry.domain == SWITCH_DOMAIN
    }

    for device in device_manager.device_map.values():
        # Old lights where in `tuya.{device_id}` format, now the DPCode is added.
        #
        # If the device is a previously supported light category and still has
        # the old format for the unique ID, migrate it to the new format.
        #
        # Previously only devices providing the SWITCH_LED DPCode were supported,
        # thus this can be added to those existing IDs.
        #
        # `tuya.{device_id}` -> `tuya.{device_id}{SWITCH_LED}`
        if (
            device.category in ("dc", "dd", "dj", "fs", "fwl", "jsq", "xdd", "xxj")
            and (entry := light_entries.get(f"tuya.{device.id}"))
            and f"tuya.{device.id}{DPCode.SWITCH_LED}" not in light_entries
        ):
            entity_registry.async_update_entity(
                entry.entity_id, new_unique_id=f"tuya.{device.id}{DPCode.SWITCH_LED}"
            )

        # Old switches has different formats for the unique ID, but is mappable.
        #
        # If the device is a previously supported switch category and still has
        # the old format for the unique ID, migrate it to the new format.
        #
        # `tuya.{device_id}` -> `tuya.{device_id}{SWITCH}`
        # `tuya.{device_id}_1` -> `tuya.{device_id}{SWITCH_1}`
        # ...
        # `tuya.{device_id}_6` -> `tuya.{device_id}{SWITCH_6}`
        # `tuya.{device_id}_usb1` -> `tuya.{device_id}{SWITCH_USB1}`
        # ...
        # `tuya.{device_id}_usb6` -> `tuya.{device_id}{SWITCH_USB6}`
        #
        # In all other cases, the unique ID is not changed.
        if device.category in ("bh", "cwysj", "cz", "dlq", "kg", "kj", "pc", "xxj"):
            for postfix, dpcode in (
                ("", DPCode.SWITCH),
                ("_1", DPCode.SWITCH_1),
                ("_2", DPCode.SWITCH_2),
                ("_3", DPCode.SWITCH_3),
                ("_4", DPCode.SWITCH_4),
                ("_5", DPCode.SWITCH_5),
                ("_6", DPCode.SWITCH_6),
                ("_usb1", DPCode.SWITCH_USB1),
                ("_usb2", DPCode.SWITCH_USB2),
                ("_usb3", DPCode.SWITCH_USB3),
                ("_usb4", DPCode.SWITCH_USB4),
                ("_usb5", DPCode.SWITCH_USB5),
                ("_usb6", DPCode.SWITCH_USB6),
            ):
                if (
                    entry := switch_entries.get(f"tuya.{device.id}{postfix}")
                ) and f"tuya.{device.id}{dpcode}" not in switch_entries:
                    entity_registry.async_update_entity(
                        entry.entity_id, new_unique_id=f"tuya.{device.id}{dpcode}"
                    )


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

    # pylint: disable=arguments-differ
    # Library incorrectly defines methods as 'classmethod'
    # https://github.com/tuya/tuya-iot-python-sdk/pull/48

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
