"""The blueprint integration."""

import asyncio
import logging
from typing import Any, Dict, Iterable

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import CONF_DOMAIN, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, placeholder
from homeassistant.util import yaml

DOMAIN = "blueprint"
BLUEPRINT_FOLDER = "blueprints"

CONF_BLUEPRINT = "blueprint"
CONF_INPUT = "input"

BLUEPRINT_SCHEMA = vol.Schema(
    {
        # No definition yet for the inputs.
        vol.Required(CONF_BLUEPRINT): {
            vol.Required(CONF_DOMAIN): str,
            vol.Required(CONF_INPUT): {str: vol.Any(None)},
        },
    },
    extra=vol.ALLOW_EXTRA,
)

BLUEPRINT_INSTANCE_FIELDS = {
    vol.Required(CONF_BLUEPRINT): vol.Schema(
        {
            vol.Required(CONF_NAME): cv.path,
            vol.Required(CONF_INPUT): {str: cv.match_all},
        }
    )
}


async def async_setup(hass, config):
    """Set up the blueprint integration."""
    # Register websocket APIs for frontend here.
    return True


class BlueprintException(Exception):
    """Base exception for blueprint errors."""

    def __init__(self, domain: str, blueprint_name: str, msg) -> None:
        """Initialize blueprint exception."""
        super().__init__(msg)
        self.domain = domain
        self.blueprint_name = blueprint_name


class FailedToLoad(BlueprintException):
    """When we failed to load the blueprint."""

    def __init__(self, domain: str, blueprint_name: str, exc: Exception) -> None:
        """Initialize blueprint exception."""
        super().__init__(domain, blueprint_name, f"Failed to load blueprint: {exc}")


class InvalidBlueprint(BlueprintException):
    """When we encountered an invalid blueprint."""

    def __init__(
        self,
        domain: str,
        blueprint_name: str,
        blueprint_data: Any,
        msg_or_exc: vol.Invalid,
    ):
        """Initialize an invalid blueprint error."""
        if isinstance(msg_or_exc, vol.Invalid):
            msg_or_exc = humanize_error(blueprint_data, msg_or_exc)

        super().__init__(
            domain,
            blueprint_name,
            f"Invalid blueprint: {msg_or_exc}",
        )
        self.blueprint_data = blueprint_data


class MissingPlaceholder(BlueprintException):
    """When we miss a placeholder."""

    def __init__(
        self, domain: str, blueprint_name: str, placeholder_names: Iterable[str]
    ) -> None:
        """Initialize blueprint exception."""
        super().__init__(
            domain,
            blueprint_name,
            f"Missing placeholder {', '.join(sorted(placeholder_names))}",
        )


@callback
def is_blueprint_config(config: Any) -> bool:
    """Return if it is a blueprint config."""
    return isinstance(config, dict) and CONF_BLUEPRINT in config


class Blueprint:
    """Blueprint of a configuration structure."""

    def __init__(self, domain: str, name: str, data: dict) -> None:
        """Initialize a blueprint."""
        self.domain = domain
        self.name = name
        self.data = data
        self.placeholders = placeholder.extract_placeholders(data)

        # Should we validate that all placeholders are mentioned in input?


class BlueprintInputs:
    """Inputs for a blueprint."""

    def __init__(self, blueprint: Blueprint, inputs: Dict[str, Any]) -> None:
        """Instantiate a blueprint inputs object."""
        self.blueprint = blueprint
        self.inputs = inputs

    def validate(self) -> None:
        """Validate the inputs."""
        missing = self.blueprint.placeholders - set(self.inputs)

        if missing:
            raise MissingPlaceholder(
                self.blueprint.domain, self.blueprint.name, missing
            )

        # In future we can see if entities are correct domain, areas exist etc

    @callback
    def async_substitute(self) -> dict:
        """Get the blueprint value with the inputs substituted."""
        processed = placeholder.substitute(self.blueprint.data, self.inputs)
        processed.pop(CONF_BLUEPRINT)
        return processed


class DomainBlueprints:
    """Blueprints for a specific domain."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        logger: logging.Logger,
    ) -> None:
        """Initialize a domain blueprints instance."""
        self.hass = hass
        self.domain = domain
        self.logger = logger
        self._blueprints = {}
        self._load_lock = asyncio.Lock()

    @callback
    def async_reset_cache(self) -> None:
        """Reset the blueprint cache."""
        self._blueprints = {}

    async def async_get_blueprint(self, blueprint_name: str) -> Blueprint:
        """Get a blueprint."""
        if blueprint_name in self._blueprints:
            return self._blueprints[blueprint_name]

        async with self._load_lock:
            # Check it again
            if blueprint_name in self._blueprints:
                return self._blueprints[blueprint_name]

            try:
                blueprint_data = await self.hass.async_add_executor_job(
                    yaml.load_yaml,
                    self.hass.config.path(
                        BLUEPRINT_FOLDER, self.domain, f"{blueprint_name}.yaml"
                    ),
                )
            except (HomeAssistantError, FileNotFoundError) as err:
                self._blueprints[blueprint_name] = None
                raise FailedToLoad(self.domain, blueprint_name, err) from err

            try:
                BLUEPRINT_SCHEMA(blueprint_data)
            except vol.Invalid as err:
                raise InvalidBlueprint(self.domain, blueprint_name, blueprint_data, err)

            if blueprint_data[CONF_BLUEPRINT][CONF_DOMAIN] != self.domain:
                raise InvalidBlueprint(
                    self.domain,
                    blueprint_name,
                    blueprint_data,
                    f"Found incorrect blueprint type {blueprint_data[CONF_BLUEPRINT][CONF_DOMAIN]}, expected {self.domain}",
                )

            blueprint = self._blueprints[blueprint_name] = Blueprint(
                self.domain, blueprint_name, blueprint_data
            )

            return blueprint

    async def async_inputs_from_config(self, config: dict) -> BlueprintInputs:
        """Process a blueprint config."""
        bp_conf = config[CONF_BLUEPRINT]
        blueprint = await self.async_get_blueprint(bp_conf[CONF_NAME])
        inputs = BlueprintInputs(blueprint, bp_conf[CONF_INPUT])
        inputs.validate()
        return inputs
