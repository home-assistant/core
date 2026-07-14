"""The template component."""

import asyncio
from collections.abc import Coroutine
import logging
from typing import Any

from homeassistant import config as conf_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_NAME,
    CONF_TRIGGERS,
    CONF_UNIQUE_ID,
    SERVICE_RELOAD,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import discovery
from homeassistant.helpers.device import (
    async_remove_stale_devices_links_keep_current_device,
)
from homeassistant.helpers.helper_integration import (
    async_remove_helper_config_entry_from_source_device,
)
from homeassistant.helpers.reload import async_reload_integration_platforms
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
from homeassistant.util.hass_dict import HassKey

from .const import (
    CONF_ADDITIONAL_OPTIONS,
    CONF_MAX,
    CONF_MIN,
    CONF_STEP,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import TriggerUpdateCoordinator
from .helpers import async_get_blueprints

_LOGGER = logging.getLogger(__name__)
DATA_COORDINATORS: HassKey[list[TriggerUpdateCoordinator]] = HassKey(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the template integration."""

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
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_reload_template_entities",
                translation_placeholders={"error": str(err)},
            ) from err

        integration = await async_get_integration(hass, DOMAIN)
        conf = await conf_util.async_process_component_and_handle_errors(
            hass, unprocessed_conf, integration
        )

        if conf is None:
            return

        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)

        if DOMAIN in conf:
            await _process_config(hass, conf)

        hass.bus.async_fire(f"event_{DOMAIN}_reloaded", context=call.context)

    async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _reload_config)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    # This can be removed in HA Core 2026.7
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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, (entry.options["template_type"],)
    )


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version == 1:
        if config_entry.minor_version < 2:
            # Remove the template config entry from the source device
            if source_device_id := config_entry.options.get(CONF_DEVICE_ID):
                async_remove_helper_config_entry_from_source_device(
                    hass,
                    helper_config_entry_id=config_entry.entry_id,
                    source_device_id=source_device_id,
                )
            hass.config_entries.async_update_entry(
                config_entry, version=1, minor_version=2
            )

        options = {**config_entry.options}
        # The "advanced_options" section was renamed to "additional_options"
        if (additional := options.pop("advanced_options", None)) is not None:
            options[CONF_ADDITIONAL_OPTIONS] = additional
        hass.config_entries.async_update_entry(
            config_entry, options=options, version=2, minor_version=1
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


async def _process_config(hass: HomeAssistant, hass_config: ConfigType) -> None:
    """Process config."""
    coordinators = hass.data.pop(DATA_COORDINATORS, None)

    # Remove old ones
    if coordinators:
        for coordinator in coordinators:
            await coordinator.async_shutdown()

    async def init_coordinator(
        hass: HomeAssistant, conf_section: dict[str, Any]
    ) -> TriggerUpdateCoordinator:
        coordinator = TriggerUpdateCoordinator(hass, conf_section)
        await coordinator.async_setup(hass_config)
        return coordinator

    coordinator_tasks: list[Coroutine[Any, Any, TriggerUpdateCoordinator]] = []

    for conf_section in hass_config[DOMAIN]:
        if CONF_TRIGGERS in conf_section:
            coordinator_tasks.append(init_coordinator(hass, conf_section))
            continue

        for platform_domain in PLATFORMS:
            if platform_domain in conf_section:
                hass.async_create_task(
                    discovery.async_load_platform(
                        hass,
                        platform_domain,
                        DOMAIN,
                        {
                            "unique_id": conf_section.get(CONF_UNIQUE_ID),
                            "entities": [
                                {
                                    **entity_conf,
                                    "raw_blueprint_inputs": (
                                        conf_section.raw_blueprint_inputs
                                    ),
                                    "raw_configs": conf_section.raw_config,
                                }
                                for entity_conf in conf_section[platform_domain]
                            ],
                        },
                        hass_config,
                    ),
                    eager_start=True,
                )

    if coordinator_tasks:
        hass.data[DATA_COORDINATORS] = await asyncio.gather(*coordinator_tasks)
