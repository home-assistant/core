"""Support for SmartThings Cloud."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from http import HTTPStatus
import importlib
import logging

from aiohttp.client_exceptions import ClientConnectionError, ClientResponseError
from pysmartapp.event import EVENT_TYPE_DEVICE
from pysmartthings import Attribute, Capability, SmartThings
from pysmartthings.device import DeviceEntity

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .config_flow import SmartThingsFlowHandler  # noqa: F401
from .const import (
    CONF_APP_ID,
    CONF_INSTALLED_APP_ID,
    CONF_LOCATION_ID,
    CONF_REFRESH_TOKEN,
    DATA_BROKERS,
    DATA_MANAGER,
    DOMAIN,
    EVENT_BUTTON,
    PLATFORMS,
    SIGNAL_SMARTTHINGS_UPDATE,
    TOKEN_REFRESH_INTERVAL,
)
from .smartapp import (
    format_unique_id,
    setup_smartapp,
    setup_smartapp_endpoint,
    smartapp_sync_subscriptions,
    unload_smartapp_endpoint,
    validate_installed_app,
    validate_webhook_requirements,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the SmartThings platform."""
    await setup_smartapp_endpoint(hass, False)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle migration of a previous version config entry.

    A config entry created under a previous version must go through the
    integration setup again so we can properly retrieve the needed data
    elements. Force this by removing the entry and triggering a new flow.
    """
    # Remove the entry which will invoke the callback to delete the app.
    hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
    # only create new flow if there isn't a pending one for SmartThings.
    if not hass.config_entries.flow.async_progress_by_handler(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}
            )
        )

    # Return False because it could not be migrated.
    return False


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialize config entry which represents an installed SmartApp."""
    # For backwards compat
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry,
            unique_id=format_unique_id(
                entry.data[CONF_APP_ID], entry.data[CONF_LOCATION_ID]
            ),
        )

    if not validate_webhook_requirements(hass):
        _LOGGER.warning(
            "The 'base_url' of the 'http' integration must be configured and start with"
            " 'https://'"
        )
        return False

    api = SmartThings(async_get_clientsession(hass), entry.data[CONF_ACCESS_TOKEN])

    remove_entry = False
    try:
        # See if the app is already setup. This occurs when there are
        # installs in multiple SmartThings locations (valid use-case)
        manager = hass.data[DOMAIN][DATA_MANAGER]
        smart_app = manager.smartapps.get(entry.data[CONF_APP_ID])
        if not smart_app:
            # Validate and setup the app.
            app = await api.app(entry.data[CONF_APP_ID])
            smart_app = setup_smartapp(hass, app)

        # Validate and retrieve the installed app.
        installed_app = await validate_installed_app(
            api, entry.data[CONF_INSTALLED_APP_ID]
        )

        # Get scenes
        scenes = await async_get_entry_scenes(entry, api)

        # Get SmartApp token to sync subscriptions
        token = await api.generate_tokens(
            entry.data[CONF_CLIENT_ID],
            entry.data[CONF_CLIENT_SECRET],
            entry.data[CONF_REFRESH_TOKEN],
        )
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_REFRESH_TOKEN: token.refresh_token}
        )

        # Get devices and their current status
        devices = await api.devices(location_ids=[installed_app.location_id])

        async def retrieve_device_status(device):
            try:
                await device.status.refresh()
            except ClientResponseError:
                _LOGGER.debug(
                    (
                        "Unable to update status for device: %s (%s), the device will"
                        " be excluded"
                    ),
                    device.label,
                    device.device_id,
                    exc_info=True,
                )
                devices.remove(device)

        await asyncio.gather(*(retrieve_device_status(d) for d in devices.copy()))

        # Sync device subscriptions
        await smartapp_sync_subscriptions(
            hass,
            token.access_token,
            installed_app.location_id,
            installed_app.installed_app_id,
            devices,
        )

        # Setup device broker
        broker = DeviceBroker(hass, entry, token, smart_app, devices, scenes)
        broker.connect()
        hass.data[DOMAIN][DATA_BROKERS][entry.entry_id] = broker

    except ClientResponseError as ex:
        if ex.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            _LOGGER.exception(
                (
                    "Unable to setup configuration entry '%s' - please reconfigure the"
                    " integration"
                ),
                entry.title,
            )
            remove_entry = True
        else:
            _LOGGER.debug(ex, exc_info=True)
            raise ConfigEntryNotReady from ex
    except (ClientConnectionError, RuntimeWarning) as ex:
        _LOGGER.debug(ex, exc_info=True)
        raise ConfigEntryNotReady from ex

    if remove_entry:
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        # only create new flow if there isn't a pending one for SmartThings.
        if not hass.config_entries.flow.async_progress_by_handler(DOMAIN):
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}
                )
            )
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_get_entry_scenes(entry: ConfigEntry, api):
    """Get the scenes within an integration."""
    try:
        return await api.scenes(location_id=entry.data[CONF_LOCATION_ID])
    except ClientResponseError as ex:
        if ex.status == HTTPStatus.FORBIDDEN:
            _LOGGER.exception(
                (
                    "Unable to load scenes for configuration entry '%s' because the"
                    " access token does not have the required access"
                ),
                entry.title,
            )
        else:
            raise
    return []


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS].pop(entry.entry_id, None)
    if broker:
        broker.disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Perform clean-up when entry is being removed."""
    api = SmartThings(async_get_clientsession(hass), entry.data[CONF_ACCESS_TOKEN])

    # Remove the installed_app, which if already removed raises a HTTPStatus.FORBIDDEN error.
    installed_app_id = entry.data[CONF_INSTALLED_APP_ID]
    try:
        await api.delete_installed_app(installed_app_id)
    except ClientResponseError as ex:
        if ex.status == HTTPStatus.FORBIDDEN:
            _LOGGER.debug(
                "Installed app %s has already been removed",
                installed_app_id,
                exc_info=True,
            )
        else:
            raise
    _LOGGER.debug("Removed installed app %s", installed_app_id)

    # Remove the app if not referenced by other entries, which if already
    # removed raises a HTTPStatus.FORBIDDEN error.
    all_entries = hass.config_entries.async_entries(DOMAIN)
    app_id = entry.data[CONF_APP_ID]
    app_count = sum(1 for entry in all_entries if entry.data[CONF_APP_ID] == app_id)
    if app_count > 1:
        _LOGGER.debug(
            (
                "App %s was not removed because it is in use by other configuration"
                " entries"
            ),
            app_id,
        )
        return
    # Remove the app
    try:
        await api.delete_app(app_id)
    except ClientResponseError as ex:
        if ex.status == HTTPStatus.FORBIDDEN:
            _LOGGER.debug("App %s has already been removed", app_id, exc_info=True)
        else:
            raise
    _LOGGER.debug("Removed app %s", app_id)

    if len(all_entries) == 1:
        await unload_smartapp_endpoint(hass)


class DeviceBroker:
    """Manages an individual SmartThings config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        token,
        smart_app,
        devices: Iterable,
        scenes: Iterable,
    ) -> None:
        """Create a new instance of the DeviceBroker."""
        self._hass = hass
        self._entry = entry
        self._installed_app_id = entry.data[CONF_INSTALLED_APP_ID]
        self._smart_app = smart_app
        self._token = token
        self._event_disconnect = None
        self._regenerate_token_remove = None
        self._assignments = self._assign_capabilities(devices)
        self.devices = {device.device_id: device for device in devices}
        self.scenes = {scene.scene_id: scene for scene in scenes}

    async def _event_handler(self, req, resp, app):
    """Broker for incoming events."""
    if not self._is_same_installed_app(req.installed_app_id):
        return

    updated_devices = self._process_events(req.events)
    self._fire_button_events(updated_devices)
    self._fire_push_update_events(updated_devices)

def _is_same_installed_app(self, installed_app_id: str) -> bool:
    """Check if the event is from the same installed app."""
    return installed_app_id == self._installed_app_id

def _process_events(self, events: List[Event]) -> Set[str]:
    """Process incoming events and update device statuses."""
    updated_devices = set()
    for evt in events:
        if evt.event_type != EVENT_TYPE_DEVICE:
            continue
        device = self._get_device(evt.device_id)
        if device:
            self._update_device_status(device, evt)
            updated_devices.add(device.device_id)
    return updated_devices

def _update_device_status(self, device: Device, evt: Event) -> None:
    """Update device status based on the event."""
    device.status.apply_attribute_update(
        evt.component_id,
        evt.capability,
        evt.attribute,
        evt.value,
        data=evt.data,
    )

def _fire_button_events(self, updated_devices: Set[str]) -> None:
    """Fire events for button presses."""
    for device_id in updated_devices:
        device = self._get_device(device_id)
        if self._is_button_event(device):
            self._fire_button_event(device)

def _is_button_event(self, device: Device) -> bool:
    """Check if the device update is a button event."""
    return (
        device
        and device.label
        and device.status.is_capability_supported(Capability.button)
    )

def _fire_button_event(self, device: Device) -> None:
    """Fire a button event."""
    data = {
        "component_id": device.status.component_id,
        "device_id": device.device_id,
        "location_id": device.status.location_id,
        "value": device.status.attribute_value(Attribute.button),
        "name": device.label,
        "data": device.status.data,
    }
    self._hass.bus.async_fire(EVENT_BUTTON, data)

def _fire_push_update_events(self, updated_devices: Set[str]) -> None:
    """Fire push update events for attribute changes."""
    for device_id in updated_devices:
        device = self._get_device(device_id)
        if device:
            self._fire_push_update_event(device)

def _fire_push_update_event(self, device: Device) -> None:
    """Fire a push update event for an attribute change."""
    data = {
        "location_id": device.status.location_id,
        "device_id": device.device_id,
        "component_id": device.status.component_id,
        "capability": device.status.capability,
        "attribute": device.status.attribute,
        "value": device.status.attribute_value(device.status.attribute),
        "data": device.status.data,
    }
    _LOGGER.debug("Push update received: %s", data)
    async_dispatcher_send(self._hass, SIGNAL_SMARTTHINGS_UPDATE, {device.device_id})



class SmartThingsEntity(Entity):
    """Defines a SmartThings entity."""

    _attr_should_poll = False

    def __init__(self, device: DeviceEntity) -> None:
        """Initialize the instance."""
        self._device = device
        self._dispatcher_remove = None
        self._attr_name = device.label
        self._attr_unique_id = device.device_id
        self._attr_device_info = DeviceInfo(
            configuration_url="https://account.smartthings.com",
            identifiers={(DOMAIN, device.device_id)},
            manufacturer=device.status.ocf_manufacturer_name,
            model=device.status.ocf_model_number,
            name=device.label,
            hw_version=device.status.ocf_hardware_version,
            sw_version=device.status.ocf_firmware_version,
        )

    async def async_added_to_hass(self):
        """Device added to hass."""

        async def async_update_state(devices):
            """Update device state."""
            if self._device.device_id in devices:
                await self.async_update_ha_state(True)

        self._dispatcher_remove = async_dispatcher_connect(
            self.hass, SIGNAL_SMARTTHINGS_UPDATE, async_update_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect the device when removed."""
        if self._dispatcher_remove:
            self._dispatcher_remove()
