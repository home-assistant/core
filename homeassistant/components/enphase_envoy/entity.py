"""Support for Enphase Envoy solar energy monitor."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from httpx import HTTPError
from pyenphase import EnvoyData
from pyenphase.exceptions import EnvoyError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnphaseUpdateCoordinator

ACTIONERRORS = (EnvoyError, HTTPError)


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
