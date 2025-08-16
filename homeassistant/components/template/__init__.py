"""The template component."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import logging
from typing import Any

from homeassistant import config as conf_util
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_TRIGGERS,
    CONF_UNIQUE_ID,
    SERVICE_RELOAD,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers.device import (
    async_remove_stale_devices_links_keep_current_device,
)
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.uuid import random_uuid_hex

from .const import (
    CONF_MAX,
    CONF_MIN,
    CONF_STEP,
    DATA_HASS_COORDINATORS,
    DATA_PLATFORMS,
    DOMAIN,
    PLATFORMS,
    TemplateConfig,
    TemplateModule,
)
from .coordinator import TriggerUpdateCoordinator
from .helpers import async_get_blueprints

_LOGGER = logging.getLogger(__name__)
DATA_COORDINATORS: HassKey[dict[str, TriggerUpdateCoordinator]] = HassKey(
    DATA_HASS_COORDINATORS
)
DATA_MODULE: HassKey[TemplateModule] = HassKey("template_module")


def _template_yaml_config_entry_init(hass: HomeAssistant, config: ConfigType) -> None:
    """Create the YAML config entry task for templates."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the template integration."""
    if not (config_entries := hass.config_entries.async_entries(DOMAIN)):
        # We avoid creating an import flow if its already
        # setup since it will have to import the config_flow
        # module.
        _template_yaml_config_entry_init(hass, config)
    elif not [
        config_entry
        for config_entry in config_entries
        if config_entry.source == SOURCE_IMPORT
    ]:
        _template_yaml_config_entry_init(hass, config)

    # Register template as valid domain for Blueprint
    blueprints = async_get_blueprints(hass)

    # Add some default blueprints to blueprints/template, does nothing
    # if blueprints/template already exists but still has to create
    # an executor job to check if the folder exists so we run it in a
    # separate task to avoid waiting for it to finish setting up
    # since a tracked task will be waited at the end of startup
    hass.async_create_task(blueprints.async_populate(), eager_start=True)

    if DOMAIN in config:
        await _process_config(hass, config)

    async def _reload_config(call: Event | ServiceCall) -> None:
        """Reload top-level + platforms."""
        await async_get_blueprints(hass).async_reset_cache()
        try:
            unprocessed_conf = await conf_util.async_hass_config_yaml(hass)
        except HomeAssistantError as err:
            _LOGGER.error(err)
            return

        integration = await async_get_integration(hass, DOMAIN)
        conf = await conf_util.async_process_component_and_handle_errors(
            hass, unprocessed_conf, integration
        )

        if conf is None:
            return

        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)

        if DOMAIN in conf:
            await _process_config(hass, conf)
        else:
            hass.data.pop(DATA_PLATFORMS, None)

        if module := hass.data.get(DATA_MODULE):
            await hass.config_entries.async_reload(module.entry.entry_id)

        hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

    async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _reload_config)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    if entry.source == SOURCE_IMPORT:
        # When config validation fails, DATA_PLATFORMS may not exist.
        module: TemplateModule | None
        if platforms := hass.data.get(DATA_PLATFORMS):
            hass.data[DATA_MODULE] = module = TemplateModule(
                tuple(platforms.keys()), entry
            )
            await hass.config_entries.async_forward_entry_setups(
                entry, module.platforms
            )
        elif module := hass.data.get(DATA_MODULE):
            module.platforms = ()
    else:
        async_remove_stale_devices_links_keep_current_device(
            hass,
            entry.entry_id,
            entry.options.get(CONF_DEVICE_ID),
        )

        for key in (CONF_MAX, CONF_MIN, CONF_STEP):
            if key not in entry.options:
                continue
            if isinstance(entry.options[key], str):
                raise ConfigEntryError(
                    f"The '{entry.options.get(CONF_NAME) or ''}' number template needs to "
                    f"be reconfigured, {key} must be a number, got '{entry.options[key]}'"
                )

        await hass.config_entries.async_forward_entry_setups(
            entry, (entry.options["template_type"],)
        )
        entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))

    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    platforms: tuple[str, ...]
    if entry.source == SOURCE_IMPORT:
        platforms = module.platforms if (module := hass.data.get(DATA_MODULE)) else ()
    else:
        platforms = (entry.options["template_type"],)
    return await hass.config_entries.async_unload_platforms(entry, platforms)


async def _process_config(
    hass: HomeAssistant, hass_config: dict[str, list[TemplateConfig]]
) -> None:
    """Process config."""
    coordinators = hass.data.pop(DATA_COORDINATORS, None)
    hass.data.pop(DATA_PLATFORMS, None)

    platforms: dict[str, list[ConfigType]] = {}

    # Remove old ones
    if coordinators:
        for coordinator in coordinators.values():
            coordinator.async_remove()

    async def init_coordinator(
        hass: HomeAssistant, coordinator_id: str, conf_section: TemplateConfig
    ) -> tuple[str, TriggerUpdateCoordinator]:
        coordinator = TriggerUpdateCoordinator(hass, conf_section)
        await coordinator.async_setup(hass_config)
        return coordinator_id, coordinator

    coordinator_tasks: list[
        Coroutine[Any, Any, tuple[str, TriggerUpdateCoordinator]]
    ] = []

    for conf_section in hass_config[DOMAIN]:
        # Trigger based entities.
        if CONF_TRIGGERS in conf_section:
            coordintator_id = random_uuid_hex()
            coordinator_tasks.append(
                init_coordinator(hass, coordintator_id, conf_section)
            )

            for platform_domain in PLATFORMS:
                if platform_domain in conf_section:
                    if platform_domain not in platforms:
                        platforms[platform_domain] = []

                    for entity_config in conf_section[platform_domain]:
                        platforms[platform_domain].append(
                            {"coordinator": coordintator_id, "config": entity_config}
                        )

            continue

        # Modern and Legacy state based entities.
        for platform_domain in PLATFORMS:
            if platform_domain in conf_section:
                if platform_domain not in platforms:
                    platforms[platform_domain] = []

                unique_id = conf_section.get(CONF_UNIQUE_ID)

                for entity_config in conf_section[platform_domain]:
                    platforms[platform_domain].append(
                        {
                            "unique_id": unique_id,
                            "config": {
                                **entity_config,
                                "raw_blueprint_inputs": conf_section.raw_blueprint_inputs,
                                "raw_configs": conf_section.raw_config,
                            },
                        }
                    )

    if platforms:
        hass.data[DATA_PLATFORMS] = platforms

    if coordinator_tasks:
        hass.data[DATA_COORDINATORS] = dict(await asyncio.gather(*coordinator_tasks))
