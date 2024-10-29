"""Support for Soma Smartshades."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import logging
from typing import Any

from requests import RequestException

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .utils import is_api_response_success

_LOGGER = logging.getLogger(__name__)


def soma_api_call[_SomaEntityT: SomaEntity](
    api_call: Callable[[_SomaEntityT], Coroutine[Any, Any, dict]],
) -> Callable[[_SomaEntityT], Coroutine[Any, Any, dict]]:
    """Soma api call decorator."""

    async def inner(self: _SomaEntityT) -> dict:
        response = {}
        try:
            response_from_api = await api_call(self)
        except RequestException:
            if self.api_is_available:
                _LOGGER.warning("Connection to SOMA Connect failed")
                self.api_is_available = False
        else:
            if not self.api_is_available:
                self.api_is_available = True
                _LOGGER.info("Connection to SOMA Connect succeeded")

            if not is_api_response_success(response_from_api):
                if self.is_available:
                    self.is_available = False
                    _LOGGER.warning(
                        (
                            "Device is unreachable (%s). Error while fetching the"
                            " state: %s"
                        ),
                        self.name,
                        response_from_api["msg"],
                    )
            else:
                if not self.is_available:
                    self.is_available = True
                    _LOGGER.info("Device %s is now reachable", self.name)
                response = response_from_api
        return response

    return inner


class SomaEntity(Entity):
    """Representation of a generic Soma device."""

    _attr_has_entity_name = True

    def __init__(self, device, api):
        """Initialize the Soma device."""
        self.device = device
        self.api = api
        self.current_position = 50
        self.battery_state = 0
        self.is_available = True
        self.api_is_available = True

    @property
    def available(self):
        """Return true if the last API commands returned successfully."""
        return self.is_available

    @property
    def unique_id(self):
        """Return the unique id base on the id returned by pysoma API."""
        return self.device["mac"]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes.

        Implemented by platform classes.
        """
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="Wazombi Labs",
            name=self.device["name"],
        )

    def set_position(self, position: int) -> None:
        """Set the current device position."""
        self.current_position = position
        self.schedule_update_ha_state()

    @soma_api_call
    async def get_shade_state_from_api(self) -> dict:
        """Return the shade state from the api."""
        return await self.hass.async_add_executor_job(
            self.api.get_shade_state, self.device["mac"]
        )

    @soma_api_call
    async def get_battery_level_from_api(self) -> dict:
        """Return the battery level from the api."""
        return await self.hass.async_add_executor_job(
            self.api.get_battery_level, self.device["mac"]
        )
