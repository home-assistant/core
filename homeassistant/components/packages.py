"""
Support for Packages.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/packages/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'packages'
CONF_PACKAGES = DOMAIN

_COMPONENT_SCHEMA = vol.Schema({cv.slug: vol.Any(dict, list)})

_CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({cv.slug: _COMPONENT_SCHEMA})
}, extra=vol.ALLOW_EXTRA)


def _log_error(package, component, message, *message_args):
    """Log an error while merging."""
    _LOGGER.error("Package %s setup failed. Component %s %s",
                  package, component, message.format(*message_args))


def merge_packages_config(config):
    """Merge packages into the root level config. Mutate config."""
    if CONF_PACKAGES not in config:
        return config

    _CONFIG_SCHEMA(config)

    blocked_comps = ['homeassistant']
    for pack_name, pack_conf in config[CONF_PACKAGES].items():
        for comp_name, comp_conf in pack_conf.items():
            if comp_name in blocked_comps:
                _log_error(pack_name, comp_name, "not allowed")
                continue

            if comp_name not in config:
                config[comp_name] = comp_conf
                continue

            if isinstance(config[comp_name], list):
                # Merge lists
                if not isinstance(comp_conf, list):
                    _log_error(pack_name, comp_name, "cannot be merged, "
                               "config types differs. Expected a list.")
                    continue
                for itm in comp_conf:
                    config[comp_name].append(itm)

            elif isinstance(config[comp_name], dict):
                # Merge dicts
                if not isinstance(comp_conf, dict):
                    _log_error(pack_name, comp_name, "cannot be merged, "
                               "config type differs. Expected a dict.")
                    continue
                for key, val in comp_conf.items():
                    if key in config[comp_name]:
                        _log_error(pack_name, comp_name,
                                   "duplicate key '{}'", key)
                        continue
                    config[comp_name][key] = val

            else:
                assert False, "Prevented by the Schema."

    del config[CONF_PACKAGES]

    return config
