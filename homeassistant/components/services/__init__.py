"""The Service Actions integration."""

from __future__ import annotations

from typing import Protocol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, integration_platform
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

__all__ = []


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Diagnostics from a config entry."""
    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _register_service_actions_platform
    )

    return True


class ServiceActionsProtocol(Protocol):
    """Define the format that service actions platforms can have."""

    async def async_setup_service_actions(self, hass: HomeAssistant) -> None:
        """Set up service actions for an integration."""


async def _register_service_actions_platform(
    hass: HomeAssistant, integration_domain: str, platform: ServiceActionsProtocol
) -> None:
    """Register a service actions platform."""
    await platform.async_setup_service_actions(hass)
