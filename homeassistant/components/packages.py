"""
Support for Packages.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/packages/
"""
import logging

import voluptuous as vol

from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'packages'
CONF_PACKAGES = DOMAIN

_CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.Schema({
            cv.slug: vol.Any(dict, list)
        })
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the packages component."""
    raise HomeAssistantError('Packages should not be setup')


def merge_packages_config(config):
    """Merge packages into the root level config. Mutate config."""
    if CONF_PACKAGES not in config:
        return config

    _CONFIG_SCHEMA(config)

    blocked_comps = ['homeassistant', 'groups']
    for pack_name, pack_conf in config[CONF_PACKAGES].items():
        for comp_name, comp_conf in pack_conf.items():
            if comp_name in blocked_comps:
                _LOGGER.error("Package %s setup failed, %s not allowed",
                              pack_name, comp_name)
                continue
            toplevel_name = '{} {}'.format(comp_name, pack_name)
            if toplevel_name in config:
                _LOGGER.error("Package %s, not successful, since '%s' exists",
                              pack_name, toplevel_name)
                continue
            config[toplevel_name] = comp_conf
    del config[CONF_PACKAGES]

    return config
