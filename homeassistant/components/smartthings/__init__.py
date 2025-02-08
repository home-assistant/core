"""Support for SmartThings Cloud."""

from __future__ import annotations

import asyncio
import logging

from pysmartthings import SmartThings

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LOCATION_ID
from .coordinator import (
    SmartThingsConfigEntry,
    SmartThingsData,
    SmartThingsDeviceCoordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    # Platform.CLIMATE,
    Platform.COVER,
    # Platform.FAN,
    Platform.LIGHT,
    # Platform.LOCK,
    Platform.SCENE,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: SmartThingsConfigEntry) -> bool:
    """Initialize config entry which represents an installed SmartApp."""
    client = SmartThings(
        entry.data[CONF_ACCESS_TOKEN], session=async_get_clientsession(hass)
    )

    devices = await client.get_devices(location_ids=[entry.data[CONF_LOCATION_ID]])

    coordinators = [
        SmartThingsDeviceCoordinator(hass, entry, client, device) for device in devices
    ]

    await asyncio.gather(*[coordinator.async_refresh() for coordinator in coordinators])

    scenes = {
        scene.scene_id: scene
        for scene in await client.get_scenes(location_id=entry.data[CONF_LOCATION_ID])
    }

    entry.runtime_data = SmartThingsData(
        devices=coordinators, client=client, scenes=scenes
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SmartThingsConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


# async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
#     """Perform clean-up when entry is being removed."""
#     api = SmartThings(async_get_clientsession(hass), entry.data[CONF_ACCESS_TOKEN])
#
#     # Remove the installed_app, which if already removed raises a HTTPStatus.FORBIDDEN error.
#     installed_app_id = entry.data[CONF_INSTALLED_APP_ID]
#     try:
#         await api.delete_installed_app(installed_app_id)
#     except ClientResponseError as ex:
#         if ex.status == HTTPStatus.FORBIDDEN:
#             _LOGGER.debug(
#                 "Installed app %s has already been removed",
#                 installed_app_id,
#                 exc_info=True,
#             )
#         else:
#             raise
#     _LOGGER.debug("Removed installed app %s", installed_app_id)
#
#     # Remove the app if not referenced by other entries, which if already
#     # removed raises a HTTPStatus.FORBIDDEN error.
#     all_entries = hass.config_entries.async_entries(DOMAIN)
#     app_id = entry.data[CONF_APP_ID]
#     app_count = sum(1 for entry in all_entries if entry.data[CONF_APP_ID] == app_id)
#     if app_count > 1:
#         _LOGGER.debug(
#             (
#                 "App %s was not removed because it is in use by other configuration"
#                 " entries"
#             ),
#             app_id,
#         )
#         return
#     # Remove the app
#     try:
#         await api.delete_app(app_id)
#     except ClientResponseError as ex:
#         if ex.status == HTTPStatus.FORBIDDEN:
#             _LOGGER.debug("App %s has already been removed", app_id, exc_info=True)
#         else:
#             raise
#     _LOGGER.debug("Removed app %s", app_id)
#
#     if len(all_entries) == 1:
#         await unload_smartapp_endpoint(hass)
#
#
# class DeviceBroker:
#     """Manages an individual SmartThings config entry."""
#
#     def __init__(
#         self,
#         hass: HomeAssistant,
#         entry: ConfigEntry,
#         token,
#         smart_app,
#         devices: Iterable,
#         scenes: Iterable,
#     ) -> None:
#         """Create a new instance of the DeviceBroker."""
#         self._hass = hass
#         self._entry = entry
#         self._installed_app_id = entry.data[CONF_INSTALLED_APP_ID]
#         self._smart_app = smart_app
#         self._token = token
#         self._event_disconnect = None
#         self._regenerate_token_remove = None
#         self._assignments = self._assign_capabilities(devices)
#         self.devices = {device.device_id: device for device in devices}
#         self.scenes = {scene.scene_id: scene for scene in scenes}
#
#     def _assign_capabilities(self, devices: Iterable):
#         """Assign platforms to capabilities."""
#         assignments = {}
#         for device in devices:
#             capabilities = device.capabilities.copy()
#             slots = {}
#             for platform in PLATFORMS:
#                 platform_module = importlib.import_module(
#                     f".{platform}", self.__module__
#                 )
#                 if not hasattr(platform_module, "get_capabilities"):
#                     continue
#                 assigned = platform_module.get_capabilities(capabilities)
#                 if not assigned:
#                     continue
#                 # Draw-down capabilities and set slot assignment
#                 for capability in assigned:
#                     if capability not in capabilities:
#                         continue
#                     capabilities.remove(capability)
#                     slots[capability] = platform
#             assignments[device.device_id] = slots
#         return assignments
#
#     def connect(self):
#         """Connect handlers/listeners for device/lifecycle events."""
#
#         # Setup interval to regenerate the refresh token on a periodic basis.
#         # Tokens expire in 30 days and once expired, cannot be recovered.
#         async def regenerate_refresh_token(now):
#             """Generate a new refresh token and update the config entry."""
#             await self._token.refresh(
#                 self._entry.data[CONF_CLIENT_ID],
#                 self._entry.data[CONF_CLIENT_SECRET],
#             )
#             self._hass.config_entries.async_update_entry(
#                 self._entry,
#                 data={
#                     **self._entry.data,
#                     CONF_REFRESH_TOKEN: self._token.refresh_token,
#                 },
#             )
#             _LOGGER.debug(
#                 "Regenerated refresh token for installed app: %s",
#                 self._installed_app_id,
#             )
#
#         self._regenerate_token_remove = async_track_time_interval(
#             self._hass, regenerate_refresh_token, TOKEN_REFRESH_INTERVAL
#         )
#
#         # Connect handler to incoming device events
#         self._event_disconnect = self._smart_app.connect_event(self._event_handler)
#
#     def disconnect(self):
#         """Disconnects handlers/listeners for device/lifecycle events."""
#         if self._regenerate_token_remove:
#             self._regenerate_token_remove()
#         if self._event_disconnect:
#             self._event_disconnect()
#
#     def get_assigned(self, device_id: str, platform: str):
#         """Get the capabilities assigned to the platform."""
#         slots = self._assignments.get(device_id, {})
#         return [key for key, value in slots.items() if value == platform]
#
#     def any_assigned(self, device_id: str, platform: str):
#         """Return True if the platform has any assigned capabilities."""
#         slots = self._assignments.get(device_id, {})
#         return any(value for value in slots.values() if value == platform)
#
#     async def _event_handler(self, req, resp, app):
#         """Broker for incoming events."""
#         # Do not process events received from a different installed app
#         # under the same parent SmartApp (valid use-scenario)
#         if req.installed_app_id != self._installed_app_id:
#             return
#
#         updated_devices = set()
#         for evt in req.events:
#             if evt.event_type != EVENT_TYPE_DEVICE:
#                 continue
#             if not (device := self.devices.get(evt.device_id)):
#                 continue
#             device.status.apply_attribute_update(
#                 evt.component_id,
#                 evt.capability,
#                 evt.attribute,
#                 evt.value,
#                 data=evt.data,
#             )
#
#             # Fire events for buttons
#             if (
#                 evt.capability == Capability.button
#                 and evt.attribute == Attribute.button
#             ):
#                 data = {
#                     "component_id": evt.component_id,
#                     "device_id": evt.device_id,
#                     "location_id": evt.location_id,
#                     "value": evt.value,
#                     "name": device.label,
#                     "data": evt.data,
#                 }
#                 self._hass.bus.async_fire(EVENT_BUTTON, data)
#                 _LOGGER.debug("Fired button event: %s", data)
#             else:
#                 data = {
#                     "location_id": evt.location_id,
#                     "device_id": evt.device_id,
#                     "component_id": evt.component_id,
#                     "capability": evt.capability,
#                     "attribute": evt.attribute,
#                     "value": evt.value,
#                     "data": evt.data,
#                 }
#                 _LOGGER.debug("Push update received: %s", data)
#
#             updated_devices.add(device.device_id)
#
#         async_dispatcher_send(self._hass, SIGNAL_SMARTTHINGS_UPDATE, updated_devices)
