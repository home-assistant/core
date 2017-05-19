"""Provides methods to bootstrap a home assistant instance."""

from typing import Optional
from types import ModuleType
import logging
import voluptuous as vol
from homeassistant import config as config_util
from homeassistant import core
from homeassistant import loader
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (config_per_platform, extract_domain_configs)
from homeassistant.const import PLATFORM_FORMAT

_LOGGER = logging.getLogger(__name__)


def validate_configuration():
    """Validates hass configuration."""
    hass = core.HomeAssistant()

    config_dir = config_util.get_default_config_dir()
    hass.config.config_dir = config_dir
    config_path = config_util.ensure_config_exists(config_dir)
    try:
        config = config_util.load_yaml_config_file(config_path)
    except HomeAssistantError as ex:
        print(ex)
        exit(1)

    try:
        config_util.CORE_CONFIG_SCHEMA(config[core.DOMAIN])
    except vol.error.MultipleInvalid as ex:
        print(ex)

    loader.prepare(hass)
    components = set(key.split(' ')[0] for key in config.keys()
                     if key != core.DOMAIN)

    for domain in loader.load_order_components(components):
        prepare_setup_component(hass, config, domain)


def log_exception(ex, domain, config, hass):
    """Logs exception."""
    print(ex)


def prepare_setup_platform(hass: core.HomeAssistant, config, domain: str,
                           platform_name: str) -> Optional[ModuleType]:
    """Load a platform and makes sure dependencies are setup."""

    platform_path = PLATFORM_FORMAT.format(domain, platform_name)

    platform = loader.get_platform(domain, platform_name)

    # Not found
    if platform is None:
        _LOGGER.error('Unable to find platform %s', platform_path)
        return None

    # Already loaded
    elif platform_path in hass.config.components:
        return platform

    return platform


def prepare_setup_component(hass: core.HomeAssistant, config: dict,
                            domain: str):
    """Prepare setup of a component and return processed config."""
    # pylint: disable=too-many-return-statements
    component = loader.get_component(domain)

    if hasattr(component, 'CONFIG_SCHEMA'):
        try:
            config = component.CONFIG_SCHEMA(config)
        except vol.Invalid as ex:
            log_exception(ex, domain, config, hass)
            return None

    elif hasattr(component, 'PLATFORM_SCHEMA'):
        platforms = []
        for p_name, p_config in config_per_platform(config, domain):
            # Validate component specific platform schema
            try:
                p_validated = component.PLATFORM_SCHEMA(p_config)
            except vol.Invalid as ex:
                log_exception(ex, domain, config, hass)
                continue

            # Not all platform components follow same pattern for platforms
            # So if p_name is None we are not going to validate platform
            # (the automation component is one of them)
            if p_name is None:
                platforms.append(p_validated)
                continue

            platform = prepare_setup_platform(hass, config, domain,
                                              p_name)

            if platform is None:
                continue

            # Validate platform specific schema
            if hasattr(platform, 'PLATFORM_SCHEMA'):
                try:
                    p_validated = platform.PLATFORM_SCHEMA(p_validated)
                except vol.Invalid as ex:
                    log_exception(ex, '{}.{}'.format(domain, p_name),
                                  p_validated, hass)
                    continue

            platforms.append(p_validated)

        # Create a copy of the configuration with all config for current
        # component removed and add validated config back in.
        filter_keys = extract_domain_configs(config, domain)
        config = {key: value for key, value in config.items()
                  if key not in filter_keys}
        config[domain] = platforms

    return config


if __name__ == '__main__':
    validate_configuration()
