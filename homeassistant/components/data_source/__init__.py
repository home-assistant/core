"""The Data Sources integration.

Data Sources allow integrations to provide data sources to be consumed by other
actions, scripts, etc. Integrations decide their own configuration spec exposed
via a data_source platform.

This integration provides the APIs for actions and scripts to call data sources.
"""
from __future__ import annotations

import logging
from typing import Any, Protocol, cast

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import IntegrationNotFound
from homeassistant.requirements import async_get_integration_with_requirements

from .const import DOMAIN


class InvalidDataSourceConfig(HomeAssistantError):
    """When the specified data source configuration is invalid."""


class DataSourceProtocol(Protocol):
    """Define the format of data_source modules.

    Each model defines its own DATA_SOURCE_SCHEMA and methods to provide data.
    """

    DATA_SOURCE_SCHEMA: vol.Schema

    async def async_get_data(self, hass: HomeAssistant, config: ConfigType) -> Any:
        """Provide the data for the specified data source configuration."""


async def async_get_data_source_platform(
    hass: HomeAssistant,
    domain: str,
) -> DataSourceProtocol:
    """Load device data source platform for the integration.

    Throws InvalidDataSourceConfig if the integration is not found or does not
    support the data source platform.
    """
    try:
        integration = await async_get_integration_with_requirements(hass, domain)
        platform = integration.get_platform(DOMAIN)
    except IntegrationNotFound as err:
        raise InvalidDataSourceConfig(f"Integration '{domain}' not found") from err
    except ImportError as err:
        raise InvalidDataSourceConfig(
            f"Integration '{domain}' does not support data sources"
        ) from err

    if not hasattr(platform, "async_get_data"):
        raise InvalidDataSourceConfig(f"Integration '{domain}' does not async_get_data")

    return platform


async def async_get_data_source(
    hass: HomeAssistant,
    domain: str,
    config: ConfigType,
) -> Any:
    """Populate data from a data source."""
    platform = await async_get_data_source_platform(hass, domain)
    logging.debug(platform.DATA_SOURCE_SCHEMA)
    platform.DATA_SOURCE_SCHEMA(config)
    try:
        config = cast(ConfigType, platform.DATA_SOURCE_SCHEMA(config))
    except vol.Invalid as err:
        raise InvalidDataSourceConfig(str(err)) from err
    return await platform.async_get_data(hass, config)
