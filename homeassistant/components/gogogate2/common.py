"""Common code for GogoGate2 component."""

from __future__ import annotations

from collections.abc import Mapping
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
from ismartgate.common import AbstractDoor

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DATA_UPDATE_COORDINATOR, DEVICE_TYPE_ISMARTGATE, DOMAIN
from .coordinator import DeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class StateData(NamedTuple):
    """State data for a cover entity."""

    config_unique_id: str
    unique_id: str | None
    door: AbstractDoor | None


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
            config_entry,
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
