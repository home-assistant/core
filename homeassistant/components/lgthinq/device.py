"""Implements LG ThinQ device."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.device_registry import (
    async_get as async_get_device_registry,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from thinqconnect.const import PROPERTY_READABLE, DeviceType
from thinqconnect.devices.connect_device import (
    ConnectBaseDevice,
    ConnectDeviceProfile,
)
from thinqconnect.thinq_api import ThinQApiResponse

from .const import (
    CONNECT_POLLING_INTERVAL,
    DEVICE_TYPE_API_MAP,
    DOMAIN,
    ErrorCode,
    Profile,
    ProfileMap,
    PropertyMap,
)
from .thinq import ThinQ

_LOGGER = logging.getLogger(__name__)


class LGDevice:
    """A class that implementats LG ThinQ device."""

    def __init__(
        self,
        hass: HomeAssistant,
        thinq: ThinQ,
        api: ConnectBaseDevice,
        sub_id: str | None = None,
    ):
        """Initialize device."""
        self._hass = hass
        self._thinq = thinq
        self._coordinator: DataUpdateCoordinator = None
        self._type: str = api.device_type
        self._id: str = api.device_id
        self._sub_id: str = sub_id
        self._model: str = api.model_name
        self._is_on: bool = False
        self._is_connected: bool = True

        # The device name is usually set to 'alias'.
        # But, if the sub_id exists, it will be set to 'alias {sub_id}'.
        # e.g. alias='MyWashTower', sub_id='dryer' then 'MyWashTower dryer'.
        self._name = f"{api.alias} {sub_id}" if sub_id else f"{api.alias}"

        # The unique id is usually set to 'device_id'.
        # But, if the sub_id exists, it will be set to 'device_id_{sub_id}'.
        # e.g. device_id='TQSXXXX', sub_id='dryer' then 'TQSXXXX_dryer'.
        self._unique_id: str = (
            f"{api.device_id}_{sub_id}" if sub_id else f"{api.device_id}"
        )

        # Get the api instance.
        self._api: ConnectBaseDevice = api.get_sub_device(sub_id) or api

        # Create property map form the given api instance.
        self._property_map: PropertyMap = self._retrieve_profiles(
            self.api.profiles
        )

        # A notification message is stored in this device instance instead of
        # the api instance.
        self._noti_message: str | None = None

    @property
    def hass(self) -> HomeAssistant:
        """Returns the hass instance."""
        return self._hass

    @property
    def api(self) -> ConnectBaseDevice:
        """Returns the device api."""
        return self._api

    @property
    def name(self) -> str:
        """Returns the name."""
        return self._name

    @property
    def model(self) -> str:
        """Returns the model."""
        return self._model

    @property
    def id(self) -> str:
        """Returns the device id."""
        return self._id

    @property
    def sub_id(self) -> str:
        """Returns the device sub id."""
        return self._sub_id

    @property
    def unique_id(self) -> str:
        """Returns the unique id."""
        return self._unique_id

    @property
    def type(self) -> str:
        """Returns the type of device."""
        return self._type

    @property
    def is_on(self) -> bool:
        """Check whether the device is on state or not."""
        return self._is_on

    @property
    def is_connected(self) -> bool:
        """Check whether the device is connected or not."""
        return self._is_connected

    @property
    def coordinator(self) -> DataUpdateCoordinator | None:
        """Return the DataUpdateCoordinator used by this device."""
        return self._coordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._unique_id)},
            manufacturer="LGE",
            model=self.model,
            name=self.name,
            sw_version="0.9",
        )

    @property
    def property_map(self) -> PropertyMap:
        """Returns the profile map."""
        return self._property_map

    @property
    def noti_message(self) -> str | None:
        """Returns the notification message."""
        return self._noti_message

    @noti_message.setter
    def noti_message(self, message) -> None:
        self._noti_message = message

    @property
    def tag(self) -> str:
        """Returns the tag string."""
        return f"[{self.name}]"

    def _fill_property_map_with_no_location(
        self, profiles: ConnectDeviceProfile, property_map: PropertyMap
    ) -> None:
        if profiles.properties:
            for property_list in profiles.properties.values():
                for prop in property_list:
                    try:
                        property_map[None][prop] = profiles.get_property(prop)
                    except AttributeError as e:
                        _LOGGER.error(
                            "%s Failed to get property. %s", self.tag, e
                        )
                        continue

    def _fill_property_map_from_sub_profile(
        self,
        location: str,
        properties: dict[str, list],
        sub_profile: ConnectDeviceProfile,
        property_map: PropertyMap,
    ) -> None:
        for property_list in properties.values():
            for prop in property_list:
                try:
                    if location in property_map:
                        property_map[location][prop] = (
                            sub_profile.get_property(prop)
                        )
                    else:
                        property_map[location] = {
                            prop: sub_profile.get_property(prop)
                        }

                except AttributeError as e:
                    _LOGGER.error("%s Failed to get property. %s", self.tag, e)
                    continue

    def _fill_property_map_with_location(
        self, profiles: ConnectDeviceProfile, property_map: PropertyMap
    ) -> None:
        if profiles.location_properties:
            for location, properties in profiles.location_properties.items():
                sub_profile = profiles.get_sub_profile(location)
                self._fill_property_map_from_sub_profile(
                    location, properties, sub_profile, property_map
                )

                # Errors for sub profile.
                if isinstance(sub_profile.errors, list):
                    property_map[location]["error"] = {
                        "type": "enum",
                        PROPERTY_READABLE: sub_profile.errors,
                    }

    def _retrieve_profiles(
        self, profiles: ConnectDeviceProfile
    ) -> PropertyMap:
        """Create profile map form the given api instance."""
        # The structure of the profile map is as follows:
        #
        #   profile_map: {
        #     None: {
        #       "property_name1": Profile1,
        #     }
        #     "location_name_1": {
        #       "property_name1": Profile2,
        #       "property_name2": Profile3,
        #     },
        #   }
        #
        # Note that "None" key means that profile has not any location info.
        property_map: PropertyMap = {None: {}}

        # Get properties that do not have location information.
        self._fill_property_map_with_no_location(profiles, property_map)

        # Get properties that have location information.
        self._fill_property_map_with_location(profiles, property_map)

        # Errors
        if isinstance(profiles.errors, list):
            property_map[None]["error"] = {
                "type": "enum",
                PROPERTY_READABLE: profiles.errors,
            }

        # Notification.
        if isinstance(profiles.notification, dict):
            property_map[None]["notification"] = {
                "type": "enum",
                PROPERTY_READABLE: profiles.notification.get("push"),
            }

        return property_map

    def get_profile(self, location: str, name: str) -> Profile | None:
        """Returns the profile for the given location and name."""
        profile_map: ProfileMap = self.property_map.get(location)
        return profile_map.get(name) if profile_map else None

    def get_profiles(self, name: str) -> dict[str, Profile]:
        """Returns the profile map with location as key for the given name."""
        return {
            location: profile_map.get(name)
            for location, profile_map in self.property_map.items()
            if name in profile_map
        }

    async def async_get_device_profile(self) -> dict[str, Any] | None:
        """Get the device profile from the server."""
        result: dict[str, Any] = await self._thinq.async_get_device_profile(
            self.id
        )
        profile: dict[str, Any] = (
            result.get(self.sub_id) if self.sub_id and result else result
        )

        _LOGGER.debug("%s Get device profile: %s", self.tag, result)
        return profile

    async def async_get_device_status(self) -> dict[str, Any] | None:
        """Get the device status from the server."""
        result: ThinQApiResponse = await self._thinq.async_get_device_status(
            self.id
        )
        return self.handle_api_response(result)

    async def async_post_device_status(
        self, body: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Post a device status to the server."""
        result: ThinQApiResponse = await self._thinq.async_post_device_status(
            self.id, body
        )
        return self.handle_api_response(result, handle_error=True)

    def handle_api_response(
        self, result: ThinQApiResponse, *, handle_error: bool = False
    ) -> dict[str, Any] | None:
        """Handle an api response."""
        _LOGGER.debug("%s API result: %s", self.tag, result)

        if result.status >= 200 and result.status < 300:
            return result.body

        message: str = result.error_message
        code: str = result.error_code

        # Disable entity when "Not connected device" (error_code 1222)
        self._is_connected = code != ErrorCode.NOT_CONNECTED_DEVICE

        # Raise service validation error to show error popup on frontend.
        if handle_error:
            translation_placeholders = {
                "state": (
                    message.split()[-1]
                    if code == ErrorCode.COMMAND_NOT_SUPPORTED_IN_STATE
                    or code == ErrorCode.COMMAND_NOT_SUPPORTED_IN_MODE
                    else None
                )
            }
            self.handle_error(message, code, translation_placeholders)

        return None

    def handle_error(
        self,
        message: str,
        translation_key: str | None = None,
        translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        """Hanlde an error."""
        # Rollback status data.
        self._coordinator.async_set_updated_data(None)

        # Raise an exception to show error popup on frontend.
        raise ServiceValidationError(
            message,
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
        )

    async def async_init_coordinator(self) -> None:
        """Initialize and start coordinator."""
        self._coordinator = DataUpdateCoordinator(
            self.hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.id}",
            update_method=self.async_update_status,
        )
        await self._coordinator.async_refresh()

    async def async_update_status(self) -> None:
        """Request to the server to update the status from full response data."""
        result: dict = await self.async_get_device_status()
        if result is None:
            return

        # Full response into the device api.
        self.api.set_status(result)
        self._is_connected = True

    def update_partial_status(self, response: dict[str, Any] = None) -> None:
        """Update device status from the given partial response data."""
        if response is None:
            _LOGGER.error("%s Failed to update status.", self.tag)
            return

        status: dict[str, Any] = (
            response.get(self.sub_id) if self.sub_id else response
        )
        _LOGGER.debug("%s Update status: %s", self.tag, status)

        # Partial response into the device api.
        self.api.update_status(status)
        self._is_connected = True

    def handle_device_alias_changed(self, alias: str) -> None:
        """Handle the event that the alias has changed."""
        if alias is not None:
            if self.sub_id:
                alias = f"{alias} {self.sub_id}"

            _LOGGER.debug(
                "%s Device alias has been changed: %s", self.tag, alias
            )
            self._name = alias

            # Update device registry.
            device_registry: DeviceRegistry = async_get_device_registry(
                self.hass
            )
            device_entry: DeviceEntry = device_registry.async_get_device(
                identifiers={(DOMAIN, self._unique_id)}
            )
            if device_entry is not None:
                device_registry.async_update_device(
                    device_id=device_entry.id, name=alias
                )

    def handle_notification_message(self, message: str) -> None:
        """Handle the notification message."""
        _LOGGER.debug(
            "%s Received notification message: %s", self.tag, message
        )
        self._noti_message = message

    def __str__(self) -> str:
        """Returns a string expression."""
        return f"LGDevice:{self.name}(type={self.type}, id={self.id})"


async def async_setup_lg_device(
    hass: HomeAssistant, thinq: ThinQ, device: dict[str, Any]
) -> list[LGDevice] | None:
    """Create LG ThinQ Device and initialize."""
    device_id: str = device.get("deviceId")
    if not device_id:
        _LOGGER.error("Failed to setup device: no device id.")
        return None

    device_info: dict[str, Any] = device.get("deviceInfo")
    if not device_info:
        _LOGGER.error("Failed to setup device(%s): no device info.", device_id)
        return None

    # Get an appropriate class constructor for the device type.
    device_type: str = device_info.get("deviceType")
    constructor = DEVICE_TYPE_API_MAP.get(device_type)
    if constructor is None:
        _LOGGER.error(
            "Failed to setup device(%s): not supported device. type=%s",
            device_id,
            device_type,
        )
        return None

    # Get a device profile from the server.
    profile = await thinq.async_get_device_profile(device_id)
    if profile is None:
        _LOGGER.error("Failed to setup device(%s): no profile.", device_id)
        return None
    device_group_id: str = device_info.get("groupId")

    # Create new device api instance.
    api: ConnectBaseDevice = (
        constructor(
            thinq_api=thinq.api,
            device_id=device_id,
            device_type=device_type,
            model_name=device_info.get("modelName"),
            alias=device_info.get("alias"),
            group_id=device_group_id,
            reportable=device_info.get("reportable"),
            profile=profile,
        )
        if device_group_id
        else constructor(
            thinq_api=thinq.api,
            device_id=device_id,
            device_type=device_type,
            model_name=device_info.get("modelName"),
            alias=device_info.get("alias"),
            reportable=device_info.get("reportable"),
            profile=profile,
        )
    )

    # Create a list of sub-devices from the profile.
    # Note that some devices may have more than two device profiles.
    # In this case we should create multiple lg device instance.
    # e.g. 'WashTower-Single-Unit' = 'WashTower{dryer}' + 'WashTower{washer}'.
    device_sub_ids: list[str] = (
        list(profile.keys())
        if device_type == DeviceType.WASHTOWER and "property" not in profile
        else [None]
    )

    # Create new lg device instances.
    lg_device_list: list[LGDevice] = []
    for sub_id in device_sub_ids:
        lg_device = LGDevice(hass, thinq, api, sub_id)
        await lg_device.async_init_coordinator()

        # Finally add a lg device into the result list.
        lg_device_list.append(lg_device)
        _LOGGER.warning("Setup lg device: %s", lg_device)

    return lg_device_list
