"""Common code for GogoGate2 component."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
import logging
from typing import Any, NamedTuple

from ismartgate import (
    AbstractGateApi,
    GogoGate2Api,
    GogoGate2InfoResponse,
    ISmartGateApi,
    ISmartGateInfoResponse,
)
from ismartgate.common import AbstractDoor, get_door_by_id

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DATA_UPDATE_COORDINATOR, DEVICE_TYPE_ISMARTGATE, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class StateData(NamedTuple):
    """State data for a cover entity."""

    config_unique_id: str
    unique_id: str | None
    door: AbstractDoor | None


class DeviceDataUpdateCoordinator(
    DataUpdateCoordinator[GogoGate2InfoResponse | ISmartGateInfoResponse]
):  # pylint: disable=hass-enforce-coordinator-module
    """Manages polling for state changes from the device."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        api: AbstractGateApi,
        *,
        name: str,
        update_interval: timedelta,
        update_method: Callable[
            [], Awaitable[GogoGate2InfoResponse | ISmartGateInfoResponse]
        ]
        | None = None,
        request_refresh_debouncer: Debouncer | None = None,
    ) -> None:
        """Initialize the data update coordinator."""
        DataUpdateCoordinator.__init__(
            self,
            hass,
            logger,
            name=name,
            update_interval=update_interval,
            update_method=update_method,
            request_refresh_debouncer=request_refresh_debouncer,
        )
        self.api = api


class GoGoGate2Entity(CoordinatorEntity[DeviceDataUpdateCoordinator]):
    """Base class for gogogate2 entities."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        data_update_coordinator: DeviceDataUpdateCoordinator,
        door: AbstractDoor,
        unique_id: str,
    ) -> None:
        """Initialize gogogate2 base entity."""
        super().__init__(data_update_coordinator)
        self._config_entry = config_entry
        self._door = door
        self._door_id = door.door_id
        self._api = data_update_coordinator.api
        self._attr_unique_id = unique_id

    @property
    def door(self) -> AbstractDoor:
        """Return the door object."""
        door = get_door_by_id(self._door.door_id, self.coordinator.data)
        self._door = door or self._door
        return self._door

    @property
    def door_status(self) -> AbstractDoor:
        """Return the door with status."""
        data = self.coordinator.data
        door_with_statuses = self._api.async_get_door_statuses_from_info(data)
        return door_with_statuses[self._door_id]

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for the controller."""
        data = self.coordinator.data
        if data.remoteaccessenabled:
            configuration_url = f"https://{data.remoteaccess}"
        else:
            configuration_url = f"http://{self._config_entry.data[CONF_IP_ADDRESS]}"
        return DeviceInfo(
            configuration_url=configuration_url,
            identifiers={(DOMAIN, str(self._config_entry.unique_id))},
            name=self._config_entry.title,
            manufacturer=MANUFACTURER,
            model=data.model,
            sw_version=data.firmwareversion,
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"door_id": self._door_id}


def get_data_update_coordinator(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> DeviceDataUpdateCoordinator:
    """Get an update coordinator."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(config_entry.entry_id, {})
    config_entry_data = hass.data[DOMAIN][config_entry.entry_id]

    if DATA_UPDATE_COORDINATOR not in config_entry_data:
        api = get_api(hass, config_entry.data)

        async def async_update_data() -> GogoGate2InfoResponse | ISmartGateInfoResponse:
            try:
                return await api.async_info()
            except Exception as exception:
                raise UpdateFailed(
                    f"Error communicating with API: {exception}"
                ) from exception

        config_entry_data[DATA_UPDATE_COORDINATOR] = DeviceDataUpdateCoordinator(
            hass,
            _LOGGER,
            api,
            # Name of the data. For logging purposes.
            name="gogogate2",
            update_method=async_update_data,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=5),
        )

    return config_entry_data[DATA_UPDATE_COORDINATOR]


def cover_unique_id(config_entry: ConfigEntry, door: AbstractDoor) -> str:
    """Generate a cover entity unique id."""
    return f"{config_entry.unique_id}_{door.door_id}"


def sensor_unique_id(
    config_entry: ConfigEntry, door: AbstractDoor, sensor_type: str
) -> str:
    """Generate a cover entity unique id."""
    return f"{config_entry.unique_id}_{door.door_id}_{sensor_type}"


def get_api(hass: HomeAssistant, config_data: Mapping[str, Any]) -> AbstractGateApi:
    """Get an api object for config data."""
    gate_class = GogoGate2Api

    if config_data[CONF_DEVICE] == DEVICE_TYPE_ISMARTGATE:
        gate_class = ISmartGateApi

    return gate_class(
        config_data[CONF_IP_ADDRESS],
        config_data[CONF_USERNAME],
        config_data[CONF_PASSWORD],
        httpx_async_client=get_async_client(hass),
    )
