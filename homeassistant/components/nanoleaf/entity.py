"""Base class for Nanoleaf entity."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from aionanoleaf2 import (
    AuthError,
    InvalidEffect,
    InvalidEmersion,
    NanoleafError,
    NoAuthToken,
)

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NanoleafCoordinator


class NanoleafEntity(CoordinatorEntity[NanoleafCoordinator]):
    """Representation of a Nanoleaf entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NanoleafCoordinator) -> None:
        """Initialize a Nanoleaf entity."""
        super().__init__(coordinator)
        self._nanoleaf = nanoleaf = coordinator.nanoleaf
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, nanoleaf.serial_no)},
            manufacturer=nanoleaf.manufacturer,
            model=nanoleaf.model,
            name=nanoleaf.name,
            sw_version=nanoleaf.firmware_version,
            configuration_url=f"http://{nanoleaf.host}",
        )


def async_handle_nanoleaf_errors[EntityT: NanoleafEntity, **P](
    func: Callable[Concatenate[EntityT, P], Coroutine[Any, Any, None]],
) -> Callable[Concatenate[EntityT, P], Coroutine[Any, Any, None]]:
    """Map aionanoleaf2 errors of an entity action to Home Assistant errors."""

    @wraps(func)
    async def wrapper(self: EntityT, /, *args: P.args, **kwargs: P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except (InvalidEffect, InvalidEmersion) as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="effect_not_supported",
            ) from err
        except (AuthError, NoAuthToken) as err:
            # The token was revoked while the integration is running.
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_token",
            ) from err
        except NanoleafError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

    return wrapper
