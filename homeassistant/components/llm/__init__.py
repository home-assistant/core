"""The LLM integration.

Owns the LLM tools platform: integrations contribute tools to the LLM APIs
through an ``<integration>/llm.py`` platform with an ``async_setup_tools`` hook,
discovered here. The framework (registry, ``Tool``, the APIs) lives in
``homeassistant.helpers.llm``; this integration owns the lifecycle, mirroring the
``intent`` helper/integration split.
"""

from typing import Protocol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


class LLMToolsPlatformProtocol(Protocol):
    """Define the format that LLM tools platforms can have."""

    async def async_setup_tools(self, hass: HomeAssistant) -> None:
        """Set up the integration's LLM tools."""


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LLM integration."""
    await async_process_integration_platforms(
        hass, DOMAIN, _async_process_llm_tools_platform
    )
    return True


async def _async_process_llm_tools_platform(
    hass: HomeAssistant, domain: str, platform: LLMToolsPlatformProtocol
) -> None:
    """Register the LLM tools of an integration."""
    await platform.async_setup_tools(hass)
