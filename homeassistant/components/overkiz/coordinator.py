"""Helpers to help coordinate updates."""
from datetime import timedelta
import json
import logging
from typing import Dict, List, Optional, Union

from aiohttp import ServerDisconnectedError
from pyhoma.client import TahomaClient
from pyhoma.enums import EventName, ExecutionState
from pyhoma.exceptions import (
    BadCredentialsException,
    MaintenanceException,
    NotAuthenticatedException,
    TooManyRequestsException,
)
from pyhoma.models import DataType, Device, Place, State

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

TYPES = {
    DataType.NONE: None,
    DataType.INTEGER: int,
    DataType.DATE: int,
    DataType.STRING: str,
    DataType.FLOAT: float,
    DataType.BOOLEAN: bool,
    DataType.JSON_ARRAY: json.loads,
    DataType.JSON_OBJECT: json.loads,
}

_LOGGER = logging.getLogger(__name__)


class OverkizDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Overkiz data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        name: str,
        client: TahomaClient,
        devices: List[Device],
        places: Place,
        update_interval: Optional[timedelta] = None,
    ):
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=update_interval,
        )

        self.data = {}
        self.original_update_interval = update_interval
        self.client = client
        self.devices: Dict[str, Device] = {d.deviceurl: d for d in devices}
        self.executions: Dict[str, Dict[str, str]] = {}
        self.areas = self._places_to_area(places)

    async def _async_update_data(self) -> Dict[str, Device]:
        """Fetch Overkiz data via event listener."""
        try:
            events = await self.client.fetch_events()
        except BadCredentialsException as exception:
            raise ConfigEntryAuthFailed() from exception
        except TooManyRequestsException as exception:
            raise UpdateFailed("Too many requests, try again later.") from exception
        except MaintenanceException as exception:
            raise UpdateFailed("Server is down for maintenance.") from exception
        except (ServerDisconnectedError, NotAuthenticatedException) as exception:
            _LOGGER.debug(exception)
            self.executions = {}
            await self.client.login()
            self.devices = await self._get_devices()
            return self.devices
        except Exception as exception:
            _LOGGER.debug(exception)
            raise UpdateFailed(exception) from exception

        for event in events:
            _LOGGER.debug(
                "%s/%s (device: %s, state: %s -> %s)",
                event.name,
                event.exec_id,
                event.deviceurl,
                event.old_state,
                event.new_state,
            )

            if event.name == EventName.DEVICE_AVAILABLE:
                self.devices[event.deviceurl].available = True

            elif event.name in [
                EventName.DEVICE_UNAVAILABLE,
                EventName.DEVICE_DISABLED,
            ]:
                self.devices[event.deviceurl].available = False

            elif event.name in [
                EventName.DEVICE_CREATED,
                EventName.DEVICE_UPDATED,
            ]:
                self.devices = await self._get_devices()

            elif event.name == EventName.DEVICE_REMOVED:
                registry = await device_registry.async_get_registry(self.hass)
                registry.async_remove_device(event.deviceurl)
                del self.devices[event.deviceurl]

            elif event.name == EventName.DEVICE_STATE_CHANGED:
                for state in event.device_states:
                    device = self.devices[event.deviceurl]
                    if state.name not in device.states:
                        device.states[state.name] = state
                    device.states[state.name].value = self._get_state(state)

            elif event.name == EventName.EXECUTION_REGISTERED:
                if event.exec_id not in self.executions:
                    self.executions[event.exec_id] = {}

                self.update_interval = timedelta(seconds=1)

            elif (
                event.name == EventName.EXECUTION_STATE_CHANGED
                and event.exec_id in self.executions
                and event.new_state in [ExecutionState.COMPLETED, ExecutionState.FAILED]
            ):
                del self.executions[event.exec_id]

        if not self.executions:
            self.update_interval = self.original_update_interval

        return self.devices

    async def _get_devices(self) -> Dict[str, Device]:
        """Fetch devices."""
        _LOGGER.debug("Fetching all devices and state via /setup/devices")
        return {d.deviceurl: d for d in await self.client.get_devices(refresh=True)}

    @staticmethod
    def _get_state(state: State) -> Union[float, int, bool, str, None]:
        """Cast string value to the right type."""
        if state.type != DataType.NONE:
            caster = TYPES.get(DataType(state.type))
            return caster(state.value)
        return state.value

    def _places_to_area(self, place):
        """Convert places with sub_places to a flat dictionary of areas."""
        areas = {}
        if isinstance(place, Place):
            areas[place.oid] = place.label

        if isinstance(place.sub_places, list):
            for sub_place in place.sub_places:
                areas.update(self._places_to_area(sub_place))

        return areas
