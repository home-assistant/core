"""Base entity for the Daikin Onecta integration."""

from typing import Never

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice


class DaikinOnectaEntity(CoordinatorEntity[OnectaDataUpdateCoordinator]):
    """Base entity for a Daikin gateway device."""

    def __init__(
        self,
        coordinator: OnectaDataUpdateCoordinator,
        device: DaikinOnectaDevice,
    ) -> None:
        """Initialize the entity with its coordinator and gateway device."""
        super().__init__(coordinator)
        self._device = device

    def _raise_service_validation_error(self, translation_key: str) -> Never:
        """Raise a translated error for an unavailable device control."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"device": self._device.name},
        )

    def _raise_command_failed(self, translation_key: str) -> Never:
        """Raise a translated error when Daikin rejects a command."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"device": self._device.name},
        )
