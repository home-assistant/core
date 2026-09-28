"""Support for Enphase Envoy solar energy monitor."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate, override

from aiohttp import ClientError
from pyenphase import EnvoyData
from pyenphase.exceptions import EnvoyError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnphaseUpdateCoordinator

ACTIONERRORS = (EnvoyError, ClientError)


class EnvoyBaseEntity(CoordinatorEntity[EnphaseUpdateCoordinator]):
    """Defines a base envoy entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Init the Enphase base entity."""
        self.entity_description = description
        serial_number = coordinator.envoy.serial_number
        assert serial_number is not None
        self.envoy_serial_num = serial_number
        super().__init__(coordinator)

    @property
    def data(self) -> EnvoyData:
        """Return envoy data."""
        data = self.coordinator.envoy.data
        assert data is not None
        return data


def exception_handler[_EntityT: EnvoyBaseEntity, **_P](
    func: Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, Any]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, None]]:
    """Decorate Enphase Envoy calls to handle exceptions.

    A decorator that wraps the passed in function, catches enphase_envoy errors.
    """

    async def handler(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except ACTIONERRORS as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_error",
                translation_placeholders={
                    "host": self.coordinator.envoy.host,
                    "args": error.args[0],
                    "action": func.__name__,
                    "entity": self.entity_id,
                },
            ) from error

    return handler


class EnvoyACBAggregateEntity(EnvoyBaseEntity):
    """Defines a base entity on the aggregate ACB device."""

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Init the ACB aggregate device entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{self.envoy_serial_num}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self.envoy_serial_num}_acb")},
            manufacturer="Enphase",
            model="ACB",
            name=f"ACB {self.envoy_serial_num}",
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, self.envoy_serial_num),
                config_entry_id=coordinator.config_entry.entry_id,
            ),
        )


class EnvoyACBAggregateControlEntity(EnvoyACBAggregateEntity):
    """Defines a control on the aggregate ACB device backed by battery inventory."""

    @property
    @override
    def available(self) -> bool:
        """Return if the ACB controls are available."""
        return super().available and bool(self.data.acb_inventory)


class EnvoyACBBatteryEntity(EnvoyBaseEntity):
    """Defines a base entity on an individual AC Battery device."""

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EntityDescription,
        serial_number: str,
    ) -> None:
        """Init the AC Battery device entity."""
        super().__init__(coordinator, description)
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer="Enphase",
            model="AC Battery",
            name=f"AC Battery {serial_number}",
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, f"{self.envoy_serial_num}_acb"),
                config_entry_id=coordinator.config_entry.entry_id,
            ),
            serial_number=serial_number,
        )
