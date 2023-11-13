"""Helper to check the configuration file."""
from __future__ import annotations

from collections import OrderedDict
import logging
import os
from pathlib import Path
from typing import NamedTuple, Self

import voluptuous as vol

from homeassistant import loader
from homeassistant.config import (  # type: ignore[attr-defined]
    CONF_CORE,
    CONF_PACKAGES,
    CORE_CONFIG_SCHEMA,
    YAML_CONFIG_FILE,
    _format_config_error,
    config_per_platform,
    extract_domain_configs,
    load_yaml_config_file,
    merge_packages_config,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.requirements import (
    RequirementsNotFound,
    async_clear_install_history,
    async_get_integration_with_requirements,
)
import homeassistant.util.yaml.loader as yaml_loader

from .typing import ConfigType


class CheckConfigError(NamedTuple):
    """Configuration check error."""

    message: str
    domain: str | None
    config: ConfigType | None


class HomeAssistantConfig(OrderedDict):
    """Configuration result with errors attribute."""

    def __init__(self) -> None:
        """Initialize HA config."""
        super().__init__()
        self.errors: list[CheckConfigError] = []
        self.warnings: list[CheckConfigError] = []

    def add_error(
        self,
        message: str,
        domain: str | None = None,
        config: ConfigType | None = None,
    ) -> Self:
        """Add an error."""
        self.errors.append(CheckConfigError(str(message), domain, config))
        return self

    @property
    def error_str(self) -> str:
        """Concatenate all errors to a string."""
        return "\n".join([err.message for err in self.errors])

    def add_warning(
        self,
        message: str,
        domain: str | None = None,
        config: ConfigType | None = None,
    ) -> Self:
        """Add a warning."""
        self.warnings.append(CheckConfigError(str(message), domain, config))
        return self

    @property
    def warning_str(self) -> str:
        """Concatenate all warnings to a string."""
        return "\n".join([err.message for err in self.warnings])


async def async_check_ha_config_file(  # noqa: C901
    hass: HomeAssistant,
) -> HomeAssistantConfig:
    """Load and check if Home Assistant configuration file is valid.

    This method is a coroutine.
    """
    result = HomeAssistantConfig()
    async_clear_install_history(hass)

    def _pack_error(
        package: str, component: str, config: ConfigType, message: str
    ) -> None:
        """Handle errors from packages: _log_pkg_error."""
        message = f"Package {package} setup failed. Component {component} {message}"
        domain = f"homeassistant.packages.{package}.{component}"
        pack_config = core_config[CONF_PACKAGES].get(package, config)
        result.add_warning(message, domain, pack_config)

    def _comp_error(ex: Exception, domain: str, component_config: ConfigType) -> None:
        """Handle errors from components: async_log_exception."""
        message = _format_config_error(ex, domain, component_config)[0]
        if domain in frontend_dependencies:
            result.add_error(message, domain, component_config)
        else:
            result.add_warning(message, domain, component_config)

    async def _get_integration(
        hass: HomeAssistant, domain: str
    ) -> loader.Integration | None:
        """Get an integration."""
        integration: loader.Integration | None = None
        try:
            integration = await async_get_integration_with_requirements(hass, domain)
        except loader.IntegrationNotFound as ex:
            # We get this error if an integration is not found. In recovery mode and
            # safe mode, this currently happens for all custom integrations. Don't
            # show errors for a missing integration in recovery mode or safe mode to
            # not confuse the user.
            if not hass.config.recovery_mode and not hass.config.safe_mode:
                result.add_warning(f"Integration error: {domain} - {ex}")
        except RequirementsNotFound as ex:
            result.add_warning(f"Integration error: {domain} - {ex}")
        return integration

    # Load configuration.yaml
    config_path = hass.config.path(YAML_CONFIG_FILE)
    try:
        if not await hass.async_add_executor_job(os.path.isfile, config_path):
            return result.add_error("File configuration.yaml not found.")

        config = await hass.async_add_executor_job(
            load_yaml_config_file,
            config_path,
            yaml_loader.Secrets(Path(hass.config.config_dir)),
        )
    except FileNotFoundError:
        return result.add_error(f"File not found: {config_path}")
    except HomeAssistantError as err:
        return result.add_error(f"Error loading {config_path}: {err}")

    # Extract and validate core [homeassistant] config
    try:
        core_config = config.pop(CONF_CORE, {})
        core_config = CORE_CONFIG_SCHEMA(core_config)
        result[CONF_CORE] = core_config
    except vol.Invalid as err:
        result.add_error(
            _format_config_error(err, CONF_CORE, core_config)[0], CONF_CORE, core_config
        )
        core_config = {}

    # Merge packages
    await merge_packages_config(
        hass, config, core_config.get(CONF_PACKAGES, {}), _pack_error
    )
    core_config.pop(CONF_PACKAGES, None)

    # Filter out repeating config sections
    components = {key.partition(" ")[0] for key in config}

    frontend_dependencies: set[str] = set()
    if "frontend" in components or "default_config" in components:
        frontend = await _get_integration(hass, "frontend")
        if frontend:
            await frontend.resolve_dependencies()
            frontend_dependencies = frontend.all_dependencies | {"frontend"}

    # Process and validate config
    for domain in components:
        if not (integration := await _get_integration(hass, domain)):
            continue

        try:
            component = integration.get_component()
        except ImportError as ex:
            result.add_warning(f"Component error: {domain} - {ex}")
            continue

        # Check if the integration has a custom config validator
        config_validator = None
        try:
            config_validator = integration.get_platform("config")
        except ImportError as err:
            # Filter out import error of the config platform.
            # If the config platform contains bad imports, make sure
            # that still fails.
            if err.name != f"{integration.pkg_path}.config":
                result.add_error(f"Error importing config platform {domain}: {err}")
                continue

        if config_validator is not None and hasattr(
            config_validator, "async_validate_config"
        ):
            try:
                result[domain] = (
                    await config_validator.async_validate_config(hass, config)
                )[domain]
                continue
            except (vol.Invalid, HomeAssistantError) as ex:
                _comp_error(ex, domain, config)
                continue
            except Exception as err:  # pylint: disable=broad-except
                logging.getLogger(__name__).exception(
                    "Unexpected error validating config"
                )
                result.add_error(
                    f"Unexpected error calling config validator: {err}",
                    domain,
                    config.get(domain),
                )
                continue

        config_schema = getattr(component, "CONFIG_SCHEMA", None)
        if config_schema is not None:
            try:
                config = config_schema(config)
                # Don't fail if the validator removed the domain from the config
                if domain in config:
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
                _comp_error(ex, domain, p_config)
                continue

            # Not all platform components follow same pattern for platforms
            # So if p_name is None we are not going to validate platform
            # (the automation component is one of them)
            if p_name is None:
                platforms.append(p_validated)
                continue

            try:
                p_integration = await async_get_integration_with_requirements(
                    hass, p_name
                )
                platform = p_integration.get_platform(domain)
            except loader.IntegrationNotFound as ex:
                # We get this error if an integration is not found. In recovery mode and
                # safe mode, this currently happens for all custom integrations. Don't
                # show errors for a missing integration in recovery mode or safe mode to
                # not confuse the user.
                if not hass.config.recovery_mode and not hass.config.safe_mode:
                    result.add_warning(f"Platform error {domain}.{p_name} - {ex}")
                continue
            except (
                RequirementsNotFound,
                ImportError,
            ) as ex:
                result.add_warning(f"Platform error {domain}.{p_name} - {ex}")
                continue

            # Validate platform specific schema
            platform_schema = getattr(platform, "PLATFORM_SCHEMA", None)
            if platform_schema is not None:
                try:
                    p_validated = platform_schema(p_validated)
                except vol.Invalid as ex:
                    _comp_error(ex, f"{domain}.{p_name}", p_config)
                    continue

            platforms.append(p_validated)

        # Remove config for current component and add validated config back in.
        for filter_comp in extract_domain_configs(config, domain):
            del config[filter_comp]
        result[domain] = platforms

    return result
