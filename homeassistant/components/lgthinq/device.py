"""Implements LG ThinQ device."""

from __future__ import annotations

import logging
from typing import Any

from thinqconnect import (
    ConnectBaseDevice,
    DeviceType,
    ThinQApi,
    ThinQAPIErrorCodes,
    ThinQAPIException,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COMPANY, DEVICE_TYPE_API_MAP, DOMAIN, NONE_KEY

_LOGGER = logging.getLogger(__name__)


class LGDevice:
    """A class that implementats LG ThinQ device."""

    def __init__(
        self,
        hass: HomeAssistant,
        thinq_api: ThinQApi,
        device_api: ConnectBaseDevice,
        sub_id: str | None = None,
    ) -> None:
        """Initialize device."""
        self._hass = hass
        self._thinq_api = thinq_api
        self._is_connected: bool = True

        # Create a data update coordinator.
        self._coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_api.device_id}",
            update_method=self.async_update_status,
        )

        # If sub_id is NONE_KEY("_") then it should be None.
        self._sub_id: str | None = None if sub_id == NONE_KEY else sub_id

        # The device name is usually set to 'alias'.
        # But, if the sub_id exists, it will be set to 'alias {sub_id}'.
        # e.g. alias='MyWashTower', sub_id='dryer' then 'MyWashTower dryer'.
        self._name = (
            f"{device_api.alias} {self._sub_id}" if self._sub_id else device_api.alias
        )

        # The unique id is usually set to 'device_id'.
        # But, if the sub_id exists, it will be set to 'device_id_{sub_id}'.
        # e.g. device_id='TQSXXXX', sub_id='dryer' then 'TQSXXXX_dryer'.
        self._unique_id: str = (
            f"{device_api.device_id}_{self._sub_id}"
            if self._sub_id
            else device_api.device_id
        )

        # Get the api instance.
        self._api: ConnectBaseDevice = (
            device_api.get_sub_device(self._sub_id) or device_api
        )

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
    def sub_id(self) -> str | None:
        """Returns the device sub id."""
        return self._sub_id

    @property
    def unique_id(self) -> str:
        """Returns the unique id."""
        return self._unique_id

    @property
    def is_connected(self) -> bool:
        """Check whether the device is connected or not."""
        return self._is_connected

    @is_connected.setter
    def is_connected(self, connected: bool) -> None:
        self._is_connected = connected

    @property
    def coordinator(self) -> DataUpdateCoordinator[dict[str, Any]]:
        """Return the DataUpdateCoordinator used by this device."""
        return self._coordinator

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Return the device information."""
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self._unique_id)},
            manufacturer=COMPANY,
            model=self._api.model_name,
            name=self.name,
        )

    @property
    def tag(self) -> str:
        """Returns the tag string."""
        return f"[{self.name}]"

    async def async_init_coordinator(self) -> None:
        """Initialize and start coordinator."""
        await self._coordinator.async_refresh()

    async def async_update_status(self) -> dict[str, Any]:
        """Request to the server to update the status from full response data."""
        try:
            result = await self._thinq_api.async_get_device_status(self.api.device_id)
        except ThinQAPIException as exc:
            if exc.code == ThinQAPIErrorCodes.NOT_CONNECTED_DEVICE:
                self._is_connected = False
            return {}

        # Full response into the device api.
        self.api.set_status(result)
        self._is_connected = True
        return result

    def __str__(self) -> str:
        """Return a string expression."""
        return f"LGDevice:{self.name}(type={self.api.device_type}, id={self.api.device_id})"


async def async_setup_lg_device(
    hass: HomeAssistant, thinq_api: ThinQApi, device: dict[str, Any]
) -> list[LGDevice] | None:
    """Create LG ThinQ Device and initialize."""
    device_id = device.get("deviceId")
    if not device_id:
        _LOGGER.error("Failed to setup device: no device id")
        return None

    device_info = device.get("deviceInfo")
    if not device_info:
        _LOGGER.error("Failed to setup device(%s): no device info", device_id)
        return None

    # Get an appropriate class constructor for the device type.
    device_type = device_info.get("deviceType")
    constructor = DEVICE_TYPE_API_MAP.get(device_type)
    if constructor is None:
        _LOGGER.error(
            "Failed to setup device(%s): not supported device. type=%s",
            device_id,
            device_type,
        )
        return None

    # Get a device profile from the server.
    try:
        profile = await thinq_api.async_get_device_profile(device_id)
    except ThinQAPIException:
        _LOGGER.warning("Failed to setup device(%s): no profile", device_id)
        return None

    device_group_id: str = device_info.get("groupId")

    # Create new device api instance.
    device_api: ConnectBaseDevice = (
        constructor(
            thinq_api=thinq_api,
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
            thinq_api=thinq_api,
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
    device_sub_ids = (
        list(profile.keys())
        if device_type == DeviceType.WASHTOWER and "property" not in profile
        else [NONE_KEY]
    )

    # Create new lg device instances.
    lg_device_list: list[LGDevice] = []
    for sub_id in device_sub_ids:
        lg_device = LGDevice(hass, thinq_api, device_api, sub_id=sub_id)
        await lg_device.async_init_coordinator()

        # Finally add a lg device into the result list.
        lg_device_list.append(lg_device)
        _LOGGER.debug("Setup lg device: %s", lg_device)

    return lg_device_list
