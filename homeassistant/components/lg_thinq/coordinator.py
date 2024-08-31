"""DataUpdateCoordinator for the LG ThinQ device."""

from __future__ import annotations

import logging
from typing import Any

from thinqconnect import ConnectBaseDevice, DeviceType, ThinQApi, ThinQAPIException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEVICE_TYPE_API_MAP, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DeviceDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """LG Device's Data Update Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
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

        # For washTower's washer or dryer
        self.sub_id = sub_id

        # The device name is usually set to 'alias'.
        # But, if the sub_id exists, it will be set to 'alias {sub_id}'.
        # e.g. alias='MyWashTower', sub_id='dryer' then 'MyWashTower dryer'.
        self.device_name = (
            f"{device_api.alias} {self.sub_id}" if self.sub_id else device_api.alias
        )

        # The unique id is usually set to 'device_id'.
        # But, if the sub_id exists, it will be set to 'device_id_{sub_id}'.
        # e.g. device_id='TQSXXXX', sub_id='dryer' then 'TQSXXXX_dryer'.
        self.unique_id = (
            f"{device_api.device_id}_{self.sub_id}"
            if self.sub_id
            else device_api.device_id
        )

        # Get the api instance.
        self.device_api = device_api.get_sub_device(self.sub_id) or device_api

    async def _async_update_data(self) -> dict[str, Any]:
        """Request to the server to update the status from full response data."""
        try:
            data = await self.device_api.thinq_api.async_get_device_status(
                self.device_api.device_id
            )
        except ThinQAPIException as exc:
            raise UpdateFailed(exc) from exc

        # Full response data into the device api.
        self.device_api.set_status(data)
        return data


async def async_setup_device_coordinator(
    hass: HomeAssistant, thinq_api: ThinQApi, device: dict[str, Any]
) -> list[DeviceDataUpdateCoordinator] | None:
    """Create DeviceDataUpdateCoordinator and device_api per device."""
    device_id = device["deviceId"]
    device_info = device["deviceInfo"]

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
        else [None]
    )

    # Create new device coordinator instances.
    coordinator_list: list[DeviceDataUpdateCoordinator] = []
    for sub_id in device_sub_ids:
        coordinator = DeviceDataUpdateCoordinator(hass, device_api, sub_id=sub_id)
        await coordinator.async_config_entry_first_refresh()

        # Finally add a device coordinator into the result list.
        coordinator_list.append(coordinator)
        _LOGGER.debug("Setup device's coordinator: %s", coordinator)

    return coordinator_list
