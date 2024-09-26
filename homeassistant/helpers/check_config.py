"""Helper to check the configuration file."""

from __future__ import annotations

from collections import OrderedDict
import logging
import os
from pathlib import Path
from types import ModuleType
from typing import NamedTuple, Self, cast

import voluptuous as vol

from homeassistant import loader
from homeassistant.config import (  # type: ignore[attr-defined]
    CONF_PACKAGES,
    CORE_CONFIG_SCHEMA,
    YAML_CONFIG_FILE,
    config_per_platform,
    extract_domain_configs,
    format_homeassistant_error,
    format_schema_error,
    load_yaml_config_file,
    merge_packages_config,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.requirements import (
    RequirementsNotFound,
    async_clear_install_history,
    async_get_integration_with_requirements,
)
import homeassistant.util.yaml.loader as yaml_loader

from . import config_validation as cv
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


class HomeAssistantConfigChecker:
    """Class to check Home Assistant configuration file."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the checker."""
        self.hass = hass
        self.config: ConfigType = {}
        self.result = HomeAssistantConfig()
        self.core_config: dict = {}
        self.frontend_dependencies: set[str] = set()
        async_clear_install_history(hass)

    def _pack_error(
        self,
        hass: HomeAssistant,  # hass is unused, but required from other function calls
        package: str,
        component: str | None,
        config: ConfigType,
        message: str,
    ) -> None:
        """Handle errors from packages."""
        message = f"Setup of package '{package}' failed: {message}"
        domain = (
            f"homeassistant.packages.{package}"
            f"{'.' + component if component is not None else ''}"
        )
        pack_config = self.core_config[CONF_PACKAGES].get(package, config)
        self.result.add_warning(message, domain, pack_config)

    def _comp_error(
        self,
        ex: vol.Invalid | HomeAssistantError,
        domain: str,
        component_config: ConfigType,
        config_to_attach: ConfigType,
    ) -> None:
        """Handle errors from components."""
        if isinstance(ex, vol.Invalid):
            message = format_schema_error(self.hass, ex, domain, component_config)
        else:
            message = format_homeassistant_error(
                self.hass, ex, domain, component_config
            )
        if domain in self.frontend_dependencies:
            self.result.add_error(message, domain, config_to_attach)
        else:
            self.result.add_warning(message, domain, config_to_attach)

    async def _get_integration(self, domain: str) -> loader.Integration | None:
        """Get an integration."""
        try:
            return await async_get_integration_with_requirements(self.hass, domain)
        except loader.IntegrationNotFound as ex:
            if not (self.hass.config.recovery_mode or self.hass.config.safe_mode):
                self.result.add_warning(f"Integration error: {domain} - {ex}")
        except RequirementsNotFound as ex:
            self.result.add_warning(f"Integration error: {domain} - {ex}")
        return None

    async def async_check_config_file(self) -> HomeAssistantConfig:
        """Load and check if Home Assistant configuration file is valid."""
        if not await self._load_config_file():
            return self.result
        await self._extract_core_config()
        await self._handle_frontend_dependencies()
        await self._process_components()
        return self.result

    async def _load_config_file(self) -> bool:
        """Load the main configuration file."""
        config_path = self.hass.config.path(YAML_CONFIG_FILE)
        try:
            if not await self.hass.async_add_executor_job(os.path.isfile, config_path):
                self.result.add_error("File configuration.yaml not found.")
                return False
            self.config = await self.hass.async_add_executor_job(
                load_yaml_config_file,
                config_path,
                yaml_loader.Secrets(Path(self.hass.config.config_dir)),
            )
            return True  # noqa: TRY300
        except FileNotFoundError:
            self.result.add_error(f"File not found: {config_path}")
        except HomeAssistantError as err:
            self.result.add_error(f"Error loading {config_path}: {err}")
        return False

    async def _extract_core_config(self) -> None:
        """Extract and validate core [homeassistant] config."""
        self.core_config = self.config.pop(HOMEASSISTANT_DOMAIN, {})
        try:
            self.core_config = CORE_CONFIG_SCHEMA(self.core_config)
            self.result[HOMEASSISTANT_DOMAIN] = self.core_config
            packages = self.core_config.get(CONF_PACKAGES, {})
            await merge_packages_config(
                self.hass, self.config, packages, self._pack_error
            )
        except vol.Invalid as err:
            self.result.add_error(
                format_schema_error(
                    self.hass, err, HOMEASSISTANT_DOMAIN, self.core_config
                ),
                HOMEASSISTANT_DOMAIN,
                self.core_config,
            )
            self.core_config = {}
        self.core_config.pop(CONF_PACKAGES, None)

    async def _handle_frontend_dependencies(self) -> None:
        """Handle frontend dependencies if necessary."""
        components = {cv.domain_key(key) for key in self.config}
        if "frontend" in components or "default_config" in components:
            frontend = await self._get_integration("frontend")
            if frontend:
                await frontend.resolve_dependencies()
                self.frontend_dependencies = frontend.all_dependencies | {"frontend"}

    async def _process_components(self) -> None:
        """Process and validate all components."""
        components = {cv.domain_key(key) for key in self.config}
        for domain in components:
            await self._process_domain(domain)

    async def _process_domain(self, domain: str) -> None:
        """Process a single component domain."""
        integration = await self._get_integration(domain)
        if not integration:
            return
        component = await self._get_component(integration, domain)
        if not component:
            return
        if await self._validate_with_config_platform(integration, domain):
            return
        if await self._validate_with_config_schema(component, domain):
            return
        await self._process_platforms(domain, component)

    async def _get_component(
        self, integration: loader.Integration, domain: str
    ) -> loader.ComponentProtocol | None:
        """Get the component from the integration."""
        try:
            return await integration.async_get_component()
        except ImportError as ex:
            self.result.add_warning(f"Component error: {domain} - {ex}")
        return None

    async def _validate_with_config_platform(
        self, integration: loader.Integration, domain: str
    ) -> bool:
        """Validate using the config platform if available."""
        if not integration.platforms_exists(("config",)):
            return False
        try:
            config_validator = await integration.async_get_platform("config")
        except ImportError as err:
            if err.name != f"{integration.pkg_path}.config":
                self.result.add_error(
                    f"Error importing config platform {domain}: {err}"
                )
            return True
        if hasattr(config_validator, "async_validate_config"):
            await self._run_config_validator(config_validator, domain)
            return True
        return False

    async def _run_config_validator(
        self, config_validator: ModuleType, domain: str
    ) -> None:
        """Run the custom config validator."""
        try:
            validated = await config_validator.async_validate_config(
                self.hass, self.config
            )
            self.result[domain] = validated[domain]
        except (vol.Invalid, HomeAssistantError) as ex:
            self._comp_error(ex, domain, self.config, self.config[domain])
        except Exception as err:  # noqa: BLE001
            logging.getLogger(__name__).exception("Unexpected error validating config")
            self.result.add_error(
                f"Unexpected error calling config validator: {err}",
                domain,
                self.config.get(domain),
            )

    async def _validate_with_config_schema(
        self, component: loader.ComponentProtocol | None, domain: str
    ) -> bool:
        """Validate using the component's CONFIG_SCHEMA if available."""
        config_schema = getattr(component, "CONFIG_SCHEMA", None)
        if config_schema is None:
            return False
        try:
            validated_config = await cv.async_validate(
                self.hass, config_schema, self.config
            )
            if domain in validated_config:
                self.result[domain] = validated_config[domain]
        except vol.Invalid as ex:
            self._comp_error(ex, domain, self.config, self.config[domain])
        return True

    async def _process_platforms(
        self, domain: str, component: loader.ComponentProtocol | None
    ) -> None:
        """Process platforms for the component."""
        platform_schema = getattr(
            component,
            "PLATFORM_SCHEMA_BASE",
            getattr(component, "PLATFORM_SCHEMA", None),
        )
        if platform_schema is None:
            return
        platforms = []
        for p_name, p_config in config_per_platform(self.config, domain):
            p_validated = await self._validate_platform_schema(
                platform_schema, p_config, domain
            )  # type: ignore[no-any-return, unused-ignore]
            if p_validated is None:
                continue
            if p_name is None:
                platforms.append(p_validated)
                continue
            platform = await self._get_platform(domain, p_name)
            if platform is None:
                continue
            platform_schema = getattr(platform, "PLATFORM_SCHEMA", None)

            if platform_schema is not None:
                p_validated = self._validate_platform_specific_schema(
                    platform_schema, p_validated, domain, p_name, p_config
                )
                if p_validated is None:
                    continue

            platforms.append(p_validated)
        self._finalize_platforms_config(domain, platforms)

    async def _validate_platform_schema(
        self,
        platform_schema: vol.Schema,  # noqa: F821
        p_config: ConfigType,
        domain: str,
    ) -> ConfigType | None:
        """Validate the platform schema."""
        try:
            return cast(
                ConfigType,
                await cv.async_validate(self.hass, platform_schema, p_config),
            )
        except vol.Invalid as ex:
            self._comp_error(ex, domain, p_config, p_config)
        return None

    async def _get_platform(self, domain: str, p_name: str) -> ModuleType | None:
        """Get the platform."""
        try:
            p_integration = await async_get_integration_with_requirements(
                self.hass, p_name
            )
            return await p_integration.async_get_platform(domain)
        except loader.IntegrationNotFound as ex:
            if not (self.hass.config.recovery_mode or self.hass.config.safe_mode):
                self.result.add_warning(
                    f"Platform error '{domain}' from integration '{p_name}' - {ex}"
                )
        except (RequirementsNotFound, ImportError) as ex:
            self.result.add_warning(
                f"Platform error '{domain}' from integration '{p_name}' - {ex}"
            )
        return None

    def _validate_platform_specific_schema(
        self,
        platform_schema: vol.Schema,
        p_validated: ConfigType,
        domain: str,
        p_name: str,
        p_config: ConfigType,
    ) -> ConfigType | None:
        """Validate the platform-specific schema."""
        try:
            return cast(ConfigType, platform_schema(p_validated))
        except vol.Invalid as ex:
            self._comp_error(ex, f"{domain}.{p_name}", p_config, p_config)
            return None

    def _finalize_platforms_config(self, domain: str, platforms: list) -> None:
        """Finalize the platforms configuration."""
        for filter_comp in extract_domain_configs(self.config, domain):
            del self.config[filter_comp]
        self.result[domain] = platforms


async def async_check_ha_config_file(
    hass: HomeAssistant,
) -> HomeAssistantConfig:
    """Load and check if Home Assistant configuration file is valid."""
    checker = HomeAssistantConfigChecker(hass)
    return await checker.async_check_config_file()
