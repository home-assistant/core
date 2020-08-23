"""The template component."""

import logging

from homeassistant import config as conf_util
from homeassistant.const import SERVICE_RELOAD
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform, entity_platform
from homeassistant.loader import async_get_integration

from .const import DOMAIN, EVENT_TEMPLATE_RELOADED, PLATFORM_STORAGE_KEY

_LOGGER = logging.getLogger(__name__)


async def _async_setup_reload_service(hass):
    if hass.services.has_service(DOMAIN, SERVICE_RELOAD):
        return

    async def _reload_config(call):
        """Reload the template platform config."""

        try:
            unprocessed_conf = await conf_util.async_hass_config_yaml(hass)
        except HomeAssistantError as err:
            _LOGGER.error(err)
            return

        for platform in hass.data[PLATFORM_STORAGE_KEY]:

            integration = await async_get_integration(hass, platform.domain)

            conf = await conf_util.async_process_component_config(
                hass, unprocessed_conf, integration
            )

            if not conf:
                continue

            await platform.async_reset()

            # Extract only the config for template, ignore the rest.
            for p_type, p_config in config_per_platform(conf, platform.domain):
                if p_type != DOMAIN:
                    continue

                entities = await platform.platform.async_create_entities(hass, p_config)

                await platform.async_add_entities(entities)

        hass.bus.async_fire(EVENT_TEMPLATE_RELOADED, context=call.context)

    hass.helpers.service.async_register_admin_service(
        DOMAIN, SERVICE_RELOAD, _reload_config
    )


async def async_setup_platform_reloadable(hass):
    """Template platform with reloadability."""

    await _async_setup_reload_service(hass)

    platform = entity_platform.current_platform.get()

    if platform not in hass.data.setdefault(PLATFORM_STORAGE_KEY, []):
        hass.data[PLATFORM_STORAGE_KEY].append(platform)
