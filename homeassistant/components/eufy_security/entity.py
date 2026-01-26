"""Base class for Eufy Security entities."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import logging
from typing import Any, Concatenate

from eufy_security import Camera, EufySecurityError, InvalidCredentialsError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import EufySecurityCoordinator

_LOGGER = logging.getLogger(__name__)


def exception_wrap[_EufyEntityT: EufySecurityEntity, **_P, _R](
    async_func: Callable[Concatenate[_EufyEntityT, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[_EufyEntityT, _P], Coroutine[Any, Any, _R]]:
    """Define a wrapper to catch exceptions and raise HomeAssistant errors."""

    async def _wrap(self: _EufyEntityT, /, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await async_func(self, *args, **kwargs)
        except InvalidCredentialsError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except EufySecurityError as err:
            _LOGGER.debug(
                "Error calling %s in platform %s: %s",
                async_func.__name__,
                self.platform,
                err,
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err

    return _wrap


class EufySecurityEntity(CoordinatorEntity[EufySecurityCoordinator]):
    """Base implementation for Eufy Security device."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EufySecurityCoordinator,
        camera: Camera,
    ) -> None:
        """Initialize a Eufy Security entity."""
        super().__init__(coordinator, context=camera.serial)
        self._camera = camera
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, camera.serial)},
            manufacturer="Eufy",
            model=camera.model,
            name=camera.name,
            sw_version=camera.software_version,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._camera.serial in self.coordinator.data.get("cameras", {})
        )
