"""Helper methods for components within Home Assistant."""
import re

from homeassistant.const import CONF_PLATFORM


def validate_config(config, items, logger):
    """Validate if all items are available in the configuration.

    config is the general dictionary with all the configurations.
    items is a dict with per domain which attributes we require.
    logger is the logger from the caller to log the errors to.

    Return True if all required items were found.
    """
    errors_found = False
    for domain in items.keys():
        config.setdefault(domain, {})

        errors = [item for item in items[domain] if item not in config[domain]]

        if errors:
            logger.error(
                "Missing required configuration items in {}: {}".format(
                    domain, ", ".join(errors)))

            errors_found = True

    return not errors_found


def config_per_platform(config, domain):
    """Generator to break a component config into different platforms.

    For example, will find 'switch', 'switch 2', 'switch 3', .. etc
    """
    for config_key in extract_domain_configs(config, domain):
        platform_config = config[config_key]
        if not isinstance(platform_config, list):
            platform_config = [platform_config]

        for item in platform_config:
            platform = None if item is None else item.get(CONF_PLATFORM)
            yield platform, item


def extract_domain_configs(config, domain):
    """Extract keys from config for given domain name."""
    pattern = re.compile(r'^{}(| .+)$'.format(domain))
    return [key for key in config.keys() if pattern.match(key)]
