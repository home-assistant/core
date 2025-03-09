"""Support for Aqara Smart devices."""
from __future__ import annotations

from http import HTTPStatus
import logging
from typing import NamedTuple

from aiohttp.client_exceptions import ClientConnectionError, ClientResponseError
from aqara_iot import (
    AqaraDeviceListener,
    AqaraDeviceManager,
    AqaraHomeManager,
    AqaraOpenAPI,
    AqaraOpenMQ,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send

from .const import (
    AQARA_DISCOVERY_NEW,
    AQARA_HA_SIGNAL_REGISTER_POINT,
    AQARA_HA_SIGNAL_UPDATE_ENTITY,
    AQARA_HA_SIGNAL_UPDATE_POINT_VALUE,
    CONF_COUNTRY_CODE,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


class HomeAssistantAqaraData(NamedTuple):
    """Aqara data stored in the Home Assistant data object."""

    device_listener: DeviceListener
    device_manager: AqaraDeviceManager
    home_manager: AqaraHomeManager
    aqara_mqtt_client: AqaraOpenMQ


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup hass config entry."""
    hass.data.setdefault(DOMAIN, {})

    api = AqaraOpenAPI(entry.data[CONF_COUNTRY_CODE])

    try:
        response = await hass.async_add_executor_job(
            api.get_auth,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            "",
        )

    except ClientResponseError as ex:
        if ex.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            _LOGGER.exception(
                "Unable to setup configuration entry '%s' - please reconfigure the integration",
                entry.title,
            )
        else:
            _LOGGER.debug(ex, exc_info=True)
            raise ConfigEntryAuthFailed(ex) from ex

    except (ClientConnectionError, RuntimeWarning) as ex:
        _LOGGER.debug(ex, exc_info=True)
        raise ConfigEntryNotReady from ex

    if response is False:
        _LOGGER.error(
            "Unable to setup configuration entry,please reconfigure the integration"
        )
        raise ConfigEntryAuthFailed("please reconfigure the integration")

    device_manager = AqaraDeviceManager(api)

    home_manager = AqaraHomeManager(api, device_manager)

    mqtt_client = AqaraOpenMQ()
    mqtt_client.set_get_config(device_manager.config_mqtt_add)
    mqtt_client.add_message_listener(device_manager.on_message)
    mqtt_client.start()

    listener = DeviceListener(hass)

    device_manager.add_device_listener(listener)

    hass.data[DOMAIN][entry.entry_id] = HomeAssistantAqaraData(
        device_listener=listener,
        device_manager=device_manager,
        home_manager=home_manager,
        aqara_mqtt_client=mqtt_client,
    )

    # Get devices & clean up device entities
    await hass.async_add_executor_job(home_manager.update_device_cache)
    await hass.async_add_executor_job(home_manager.update_location_info)
    await cleanup_device_registry(hass, device_manager)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def cleanup_device_registry(
    hass: HomeAssistant, device_manager: AqaraDeviceManager
) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""
    device_registry = dr.async_get(hass)
    for dev_id, device_entry in list(device_registry.devices.items()):
        for item in device_entry.identifiers:
            if DOMAIN == item[0] and device_manager.get_point(item[1]) is None:
                device_registry.async_remove_device(dev_id)
                break


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the Aqara platforms."""
    unload = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload:
        hass_data: HomeAssistantAqaraData = hass.data[DOMAIN][entry.entry_id]
        hass_data.aqara_mqtt_client.stop()
        hass_data.device_manager.remove_device_listener(hass_data.device_listener)

        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload


class DeviceListener(AqaraDeviceListener):
    """Device Update Listener."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Init DeviceListener."""
        self.hass = hass
        self.point_ids: set[str] = set()
        self.device_registry = dr.async_get(hass)
        self.nouse_point_ids: set[str] = set()
        async_dispatcher_connect(
            self.hass,
            AQARA_HA_SIGNAL_REGISTER_POINT,
            self.async_register_point,
        )

    def async_register_point(self, point_id):
        """Add point id to point_ids."""
        self.point_ids.add(point_id)

    def update_device(self, device) -> None:
        """Update device status."""
        if device.id in self.point_ids:

            dispatcher_send(
                self.hass,
                f"{AQARA_HA_SIGNAL_UPDATE_POINT_VALUE}_{device.id}",
                device,
            )
            dispatcher_send(
                self.hass,
                f"{AQARA_HA_SIGNAL_UPDATE_ENTITY}_{device.id}",
            )

    def add_device(self, device) -> None:
        """Add device added listener."""
        # Ensure the device isn't present stale
        self.hass.add_job(self.async_remove_device, device.id)

        self.point_ids.add(device.id)

        # the point.did not point.id
        dispatcher_send(self.hass, AQARA_DISCOVERY_NEW, [device.did])

    def remove_device(self, device_id) -> None:
        """Add device removed listener."""
        self.hass.add_job(self.async_remove_device, device_id)

    @callback
    def async_remove_device(self, hass_device_id: str) -> None:
        """Remove device from Home Assistant."""
        _LOGGER.debug("Remove device: %s", hass_device_id)

        device_entry = self.device_registry.async_get_device(
            identifiers={(DOMAIN, hass_device_id)}
        )
        if device_entry is not None:
            self.device_registry.async_remove_device(device_entry.id)
            self.point_ids.discard(hass_device_id)
            self.nouse_point_ids.discard(hass_device_id)
