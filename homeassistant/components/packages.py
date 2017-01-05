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

# A list of components that are allowed to be in packages
# Typically hub type components where merging config makes no sense
_ALLOWED_COMPS = (
    'automation', 'binary_sensor', 'fan', 'group', 'input_boolean',
    'input_select', 'input_slider', 'camera', 'light', 'panel_custom',
    'panel_iframe', 'sensor', 'script', 'switch', 'zone')

_COMPONENT_SCHEMA = vol.Schema({vol.In(_ALLOWED_COMPS): vol.Any(dict, list)})

_CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({cv.slug: _COMPONENT_SCHEMA})
}, extra=vol.ALLOW_EXTRA)


def _log_error(package, component, config, message):
    """Log an error while merging."""
    message = "Package {} setup failed. Component {} {}".format(
        package, component, message)

    pack_config = config[DOMAIN].get(package, config)
    message += " (See {}:{}). ".format(
        getattr(pack_config, '__config_file__', '?'),
        getattr(pack_config, '__line__', '?'))

    _LOGGER.error(message)


def merge_packages_config(config):
    """Merge packages into the root level config. Mutate config."""
    if DOMAIN not in config:
        return config

    _CONFIG_SCHEMA(config)

    for pack_name, pack_conf in config[DOMAIN].items():
        for comp_name, comp_conf in pack_conf.items():
            if comp_name in blocked_comps:
                _log_error(pack_name, comp_name, config, "not allowed")
                continue

            if comp_name not in config:
                config[comp_name] = comp_conf
                continue

            if isinstance(config[comp_name], list):
                # Merge lists
                if not isinstance(comp_conf, list):
                    _log_error(pack_name, comp_name, config, "cannot be merged"
                               ", config types differs. Expected a list.")
                    continue
                for itm in comp_conf:
                    config[comp_name].append(itm)

            elif isinstance(config[comp_name], dict):
                # Merge dicts
                if not isinstance(comp_conf, dict):
                    _log_error(pack_name, comp_name, config, "cannot be merged"
                               ", config type differs. Expected a dict.")
                    continue
                for key, val in comp_conf.items():
                    if key in config[comp_name]:
                        _log_error(pack_name, comp_name, config,
                                   "duplicate key '{}'".format(key))
                        continue
                    config[comp_name][key] = val

            else:
                assert False, "Prevented by the Schema."

    del config[DOMAIN]

    return config
