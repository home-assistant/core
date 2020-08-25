"""Class to reload platforms."""

import logging
from typing import Optional

from homeassistant import config as conf_util
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform
from homeassistant.helpers.entity_platform import DATA_ENTITY_PLATFORM, EntityPlatform
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import async_get_integration

_LOGGER = logging.getLogger(__name__)


async def async_reload_integration_platforms(
    hass: HomeAssistantType, integration_name: str, integration_platforms: str
) -> None:
    """Reload an integration's platforms.

    The platform must support being re-setup.

    This functionality is only intended to be used for integrations that process
    Home Assistant data and make this available to other integrations.

    Examples are template, stats, derivative, utility meter.
    """
    try:
        unprocessed_conf = await conf_util.async_hass_config_yaml(hass)
    except HomeAssistantError as err:
        _LOGGER.error(err)
        return

    for integration_platform in integration_platforms:
        platform = async_get_platform(hass, integration_name, integration_platform)

        if not platform:
            continue

        integration = await async_get_integration(hass, integration_platform)

        conf = await conf_util.async_process_component_config(
            hass, unprocessed_conf, integration
        )

        if not conf:
            continue

        await platform.async_reset()

        # Extract only the config for template, ignore the rest.
        for p_type, p_config in config_per_platform(conf, integration_platform):
            if p_type != integration_name:
                continue

            await platform.async_setup(p_config)  # type: ignore


@callback
def async_get_platform(
    hass: HomeAssistantType, integration_name: str, integration_platform_name: str
) -> Optional[EntityPlatform]:
    """Find an existing platform."""
    for integration_platform in hass.data[DATA_ENTITY_PLATFORM][integration_name]:
        if integration_platform.domain == integration_platform_name:
            platform: EntityPlatform = integration_platform
            return platform

    return None
