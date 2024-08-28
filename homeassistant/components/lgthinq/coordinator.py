"""DataUpdateCoordinator for the LG ThinQ device."""

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
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COMPANY, DEVICE_TYPE_API_MAP, DOMAIN, NONE_KEY

_LOGGER = logging.getLogger(__name__)


class DeviceDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """LG Device's Data Update Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        thinq_api: ThinQApi,
        device_api: ConnectBaseDevice,
        *,
        sub_id: str | None = None,
    ) -> None:
        """Initialize data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_api.device_id}",
        )
        self._hass = hass
        self._thinq_api = thinq_api
        self._is_connected = True

        # If sub_id is NONE_KEY("_") then it should be None.
        self._sub_id = None if sub_id == NONE_KEY else sub_id

        # The device name is usually set to 'alias'.
        # But, if the sub_id exists, it will be set to 'alias {sub_id}'.
        # e.g. alias='MyWashTower', sub_id='dryer' then 'MyWashTower dryer'.
        self._device_name = (
            f"{device_api.alias} {self._sub_id}" if self._sub_id else device_api.alias
        )

        # The unique id is usually set to 'device_id'.
        # But, if the sub_id exists, it will be set to 'device_id_{sub_id}'.
        # e.g. device_id='TQSXXXX', sub_id='dryer' then 'TQSXXXX_dryer'.
        self._unique_id = (
            f"{device_api.device_id}_{self._sub_id}"
            if self._sub_id
            else device_api.device_id
        )

        # Get the api instance.
        self._device_api = device_api.get_sub_device(self._sub_id) or device_api

    @property
    def thinq_api(self) -> ThinQApi:
        """Returns the thinq api."""
        return self._thinq_api

    @property
    def device_api(self) -> ConnectBaseDevice:
        """Returns the device api."""
        return self._device_api

    @property
    def device_name(self) -> str:
        """Returns the device name."""
        return self._device_name

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
    def device_info(self) -> dr.DeviceInfo:
        """Return the device information."""
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer=COMPANY,
            model=self.device_api.model_name,
            name=self.device_name,
        )

    @property
    def tag(self) -> str:
        """Returns the tag string."""
        return f"[{self.device_name}]"

    async def _async_update_data(self) -> dict[str, Any]:
        """Request to the server to update the status from full response data."""
        try:
            data = await self.thinq_api.async_get_device_status(
                self.device_api.device_id
            )
        except ThinQAPIException as exc:
            if exc.code == ThinQAPIErrorCodes.NOT_CONNECTED_DEVICE:
                self.is_connected = False
            return {}

        # Full response into the device api.
        self.device_api.set_status(data)
        self.is_connected = True
        return data

    def __str__(self) -> str:
        """Return a string expression."""
        return (
            f"Coordinator:{self.device_name}"
            f"(type={self.device_api.device_type}, id={self.device_api.device_id})"
        )


async def async_setup_device_coordinator(
    hass: HomeAssistant, thinq_api: ThinQApi, device: dict[str, Any]
) -> list[DeviceDataUpdateCoordinator] | None:
    """Create DeviceDataUpdateCoordinator and device_api per device."""
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

    device_group_id = device_info.get("groupId")

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

    # Create new device coordinator instances.
    coordinator_list: list[DeviceDataUpdateCoordinator] = []
    for sub_id in device_sub_ids:
        coordinator = DeviceDataUpdateCoordinator(
            hass, thinq_api, device_api, sub_id=sub_id
        )
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            coordinator.data = {}

        # Finally add a device coordinator into the result list.
        coordinator_list.append(coordinator)
        _LOGGER.debug("Setup device's coordinator: %s", coordinator)

    return coordinator_list
