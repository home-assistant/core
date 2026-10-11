"""The template component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.helper_integration import async_remove_helper_devices
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ADDITIONAL_OPTIONS, CONF_MAX, CONF_MIN, CONF_STEP, DOMAIN
from .helpers import async_get_blueprints, process_config
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


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
        await process_config(hass, config)

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    device_id = entry.options.get(CONF_DEVICE_ID)

    # Clean up devices this helper created for previously selected source devices;
    # this can be removed in HA Core 2027.8.
    async_remove_helper_devices(
        hass,
        helper_config_entry_id=entry.entry_id,
        source_device_id=device_id,
        remove_all_devices=True,
    )

    device_registry = dr.async_get(hass)
    if (
        device_id is not None
        and device_registry.async_get(
            device_id, include_main_devices=False, include_child_devices=False
        )
        is not None
    ):
        # The device was split into one device per config entry; ask the user to
        # select a device again
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"composite_device_id_{entry.entry_id}",
            data={"entry_id": entry.entry_id},
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="composite_device_id",
            translation_placeholders={"name": entry.title},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, f"composite_device_id_{entry.entry_id}")

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


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of a config entry."""
    ir.async_delete_issue(hass, DOMAIN, f"composite_device_id_{entry.entry_id}")


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
                async_remove_helper_devices(
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
