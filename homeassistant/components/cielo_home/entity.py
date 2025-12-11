"""Base entity for Cielo integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from time import time
from typing import Any, Concatenate, Final, ParamSpec, TypeVar

from cieloconnectapi.model import CieloDevice

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CIELO_ERRORS, DOMAIN, LOGGER, TIMEOUT
from .coordinator import CieloDataUpdateCoordinator

_T = TypeVar("_T", bound="CieloDeviceBaseEntity")
_P = ParamSpec("_P")

FRESHNESS_INTERVAL: Final[int] = 5


def async_handle_api_call(
    function: Callable[Concatenate[_T, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, Any]]:
    """Decorate api calls to handle exceptions, update state, and note recent actions."""

    async def wrap_api_call(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
        """Wrap services for api calls."""
        entity: _T = args[0]
        res: Any = None

        try:
            client = getattr(entity, "_client", None)
            if client is not None:
                if entity.device_data:
                    client.device_data = entity.device_data

            async with asyncio.timeout(TIMEOUT):
                res = await function(*args, **kwargs)

        except CIELO_ERRORS as err:
            LOGGER.error("API call failed for entity %s: %s", entity.entity_id, err)
            raise HomeAssistantError from err
        except TimeoutError as err:
            LOGGER.error("API call timed out for entity %s: %s", entity.entity_id, err)
            raise HomeAssistantError("API call timed out") from err

        LOGGER.debug("API call result for entity %s: %s", entity.entity_id, res)

        if not isinstance(res, dict):
            LOGGER.error("API function did not return a dictionary: %s", res)
            return None

        data: dict[str, Any] | None = res.get("data")

        if not data:
            LOGGER.error("API call response contained no 'data' payload")
            return None

        if entity.device_data is None:
            LOGGER.error("Cannot update state: entity.device_data is None")
            return None

        # Map API data to Home Assistant entity attributes
        temp = data.get("set_point")
        mode = data.get("mode")
        fan_mode = data.get("fan_speed")
        preset_mode = data.get("preset")
        swing_mode = data.get("swing_position")
        device_power = data.get("power")

        device_on: bool | None = None
        if device_power == "on" or device_power is None:
            device_on = True
        elif device_power == "off":
            device_on = False
            mode = "off"

        # Update the internal model/device data
        entity.device_data.ac_states.update(data)

        # Update mirrored attributes
        entity.device_data.target_temp = str(temp) if temp is not None else None
        entity.device_data.hvac_mode = mode
        entity.device_data.fan_mode = fan_mode
        entity.device_data.preset_mode = preset_mode
        entity.device_data.swing_mode = swing_mode
        entity.device_data.device_on = device_on

        # Update heat/cool set points
        entity.device_data.target_heat_set_point = float(
            data.get("heat_set_point", 0.0)
        )
        entity.device_data.target_cool_set_point = float(
            data.get("cool_set_point", 0.0)
        )

        entity.last_action = data
        entity.last_action_timestamp = int(time())

        # Notify HA to update the UI
        entity.async_write_ha_state()

        # Notify the coordinator
        entity.coordinator.note_recent_action(entity._device_id, data)  # noqa: SLF001

        return data

    return wrap_api_call


class CieloBaseEntity(CoordinatorEntity[CieloDataUpdateCoordinator]):
    """Representation of a Cielo Base Entity."""

    _attr_has_entity_name: bool = True

    _device_id: str
    _client: Any
    _last_known: CieloDevice | None
    last_action: dict[str, Any] | None
    last_action_timestamp: int
    last_fetched_timestamp: int | None

    def __init__(
        self,
        coordinator: CieloDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initiate Cielo Base Entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._client = coordinator.client
        self._last_known = None
        self.last_action = None
        self.last_action_timestamp = int(time())
        self.last_fetched_timestamp = None

    @property
    def client(self) -> Any:
        """Return the API client bound to this entity's current device."""
        if self._client and self.device_data:
            self._client.device_data = self.device_data
        return self._client

    @property
    def device_data(self) -> CieloDevice | None:
        """Return the device data from the coordinator."""
        current_time = int(time())

        if (
            self._last_known is not None
            and self.last_fetched_timestamp is not None
            and (current_time - self.last_fetched_timestamp < FRESHNESS_INTERVAL)
        ):
            return self._last_known

        # Fetch from Coordinator
        data = self.coordinator.data.parsed
        device = data.get(self._device_id)

        if device is None:
            return None

        # Cache the fetched data
        self._last_known = device
        self.last_fetched_timestamp = current_time

        # Action Flicker Masking
        if (
            (current_time - self.last_action_timestamp < FRESHNESS_INTERVAL)
            and self.last_action
            and device.ac_states is not None
        ):
            device.ac_states.update(self.last_action)

        return device

    @property
    def device_info(self) -> DeviceInfo:
        """Return a basic device description for the entity's device data."""
        dev_data = self.device_data

        if dev_data is None:
            return DeviceInfo(identifiers={(DOMAIN, self._device_id)})

        return DeviceInfo(
            identifiers={(DOMAIN, dev_data.mac_address)},
            manufacturer="Cielo",
            name=dev_data.name,
        )


class CieloDeviceBaseEntity(CieloBaseEntity):
    """Representation of a Cielo Device."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device details for the device registry."""
        dev_data = self.device_data

        if dev_data is None:
            return DeviceInfo(identifiers={(DOMAIN, self._device_id)})

        return DeviceInfo(
            identifiers={(DOMAIN, dev_data.id)},
            name=dev_data.name,
            connections={(CONNECTION_NETWORK_MAC, dev_data.mac_address)},
            manufacturer="Cielo",
            configuration_url="https://home.cielowigle.com/",
            suggested_area=dev_data.name,
        )

