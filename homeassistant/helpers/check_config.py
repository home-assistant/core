"""Helper to check the configuration file."""
from collections import OrderedDict, namedtuple
from typing import List

import attr
import voluptuous as vol

from homeassistant import loader, requirements
from homeassistant.core import HomeAssistant
from homeassistant.config import (
    CONF_CORE,
    CORE_CONFIG_SCHEMA,
    CONF_PACKAGES,
    merge_packages_config,
    _format_config_error,
    find_config_file,
    load_yaml_config_file,
    extract_domain_configs,
    config_per_platform,
)

import homeassistant.util.yaml.loader as yaml_loader
from homeassistant.exceptions import HomeAssistantError


# mypy: allow-incomplete-defs, allow-untyped-calls, allow-untyped-defs
# mypy: no-warn-return-any

CheckConfigError = namedtuple("CheckConfigError", "message domain config")


@attr.s
class HomeAssistantConfig(OrderedDict):
    """Configuration result with errors attribute."""

    errors = attr.ib(default=attr.Factory(list))  # type: List[CheckConfigError]

    def add_error(self, message, domain=None, config=None):
        """Add a single error."""
        self.errors.append(CheckConfigError(str(message), domain, config))
        return self

    @property
    def error_str(self) -> str:
        """Return errors as a string."""
        return "\n".join([err.message for err in self.errors])


async def async_check_ha_config_file(hass: HomeAssistant) -> HomeAssistantConfig:
    """Load and check if Home Assistant configuration file is valid.

    This method is a coroutine.
    """
    config_dir = hass.config.config_dir
    result = HomeAssistantConfig()

    def _pack_error(package, component, config, message):
        """Handle errors from packages: _log_pkg_error."""
        message = "Package {} setup failed. Component {} {}".format(
            package, component, message
        )
        domain = "homeassistant.packages.{}.{}".format(package, component)
        pack_config = core_config[CONF_PACKAGES].get(package, config)
        result.add_error(message, domain, pack_config)

    def _comp_error(ex, domain, config):
        """Handle errors from components: async_log_exception."""
        result.add_error(_format_config_error(ex, domain, config), domain, config)

    # Load configuration.yaml
    try:
        config_path = await hass.async_add_executor_job(find_config_file, config_dir)
        if not config_path:
            return result.add_error("File configuration.yaml not found.")
        config = await hass.async_add_executor_job(load_yaml_config_file, config_path)
    except FileNotFoundError:
        return result.add_error("File not found: {}".format(config_path))
    except HomeAssistantError as err:
        return result.add_error("Error loading {}: {}".format(config_path, err))
    finally:
        yaml_loader.clear_secret_cache()

    # Extract and validate core [homeassistant] config
    try:
        core_config = config.pop(CONF_CORE, {})
        core_config = CORE_CONFIG_SCHEMA(core_config)
        result[CONF_CORE] = core_config
    except vol.Invalid as err:
        result.add_error(err, CONF_CORE, core_config)
        core_config = {}

    # Merge packages
    await merge_packages_config(
        hass, config, core_config.get(CONF_PACKAGES, {}), _pack_error
    )
    core_config.pop(CONF_PACKAGES, None)

    # Filter out repeating config sections
    components = set(key.split(" ")[0] for key in config.keys())

    # Process and validate config
    for domain in components:
        try:
            integration = await loader.async_get_integration(hass, domain)
        except loader.IntegrationNotFound:
            result.add_error("Integration not found: {}".format(domain))
            continue

        if (
            not hass.config.skip_pip
            and integration.requirements
            and not await requirements.async_process_requirements(
                hass, integration.domain, integration.requirements
            )
        ):
            result.add_error(
                "Unable to install all requirements: {}".format(
                    ", ".join(integration.requirements)
                )
            )
            continue

        try:
            component = integration.get_component()
        except ImportError:
            result.add_error("Component not found: {}".format(domain))
            continue

        config_schema = getattr(component, "CONFIG_SCHEMA", None)
        if config_schema is not None:
            try:
                config = config_schema(config)
                result[domain] = config[domain]
            except vol.Invalid as ex:
                _comp_error(ex, domain, config)
                continue

        component_platform_schema = getattr(
            component,
            "PLATFORM_SCHEMA_BASE",
            getattr(component, "PLATFORM_SCHEMA", None),
        )

        if component_platform_schema is None:
            continue

        platforms = []
        for p_name, p_config in config_per_platform(config, domain):
            # Validate component specific platform schema
            try:
                p_validated = component_platform_schema(p_config)
            except vol.Invalid as ex:
                _comp_error(ex, domain, config)
                continue

            # Not all platform components follow same pattern for platforms
            # So if p_name is None we are not going to validate platform
            # (the automation component is one of them)
            if p_name is None:
                platforms.append(p_validated)
                continue

            try:
                p_integration = await loader.async_get_integration(hass, p_name)
            except loader.IntegrationNotFound:
                result.add_error(
                    "Integration {} not found when trying to verify its {} "
                    "platform.".format(p_name, domain)
                )
                continue

            if (
                not hass.config.skip_pip
                and p_integration.requirements
                and not await requirements.async_process_requirements(
                    hass, p_integration.domain, p_integration.requirements
                )
            ):
                result.add_error(
                    "Unable to install all requirements: {}".format(
                        ", ".join(integration.requirements)
                    )
                )
                continue

            try:
                platform = p_integration.get_platform(domain)
            except ImportError:
                result.add_error("Platform not found: {}.{}".format(domain, p_name))
                continue

            # Validate platform specific schema
            platform_schema = getattr(platform, "PLATFORM_SCHEMA", None)
            if platform_schema is not None:
                try:
                    p_validated = platform_schema(p_validated)
                except vol.Invalid as ex:
                    _comp_error(ex, "{}.{}".format(domain, p_name), p_validated)
                    continue

            platforms.append(p_validated)

        # Remove config for current component and add validated config back in.
        for filter_comp in extract_domain_configs(config, domain):
            del config[filter_comp]
        result[domain] = platforms

    return result
