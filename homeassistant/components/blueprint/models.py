"""Blueprint models."""
import asyncio
import logging
import pathlib
from typing import Any, Dict, Optional, Union

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import CONF_DOMAIN, CONF_NAME, CONF_PATH
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import placeholder
from homeassistant.util import yaml

from .const import (
    BLUEPRINT_FOLDER,
    CONF_BLUEPRINT,
    CONF_INPUT,
    CONF_SOURCE_URL,
    CONF_USE_BLUEPRINT,
    DOMAIN,
)
from .errors import (
    BlueprintException,
    FailedToLoad,
    InvalidBlueprint,
    InvalidBlueprintInputs,
    MissingPlaceholder,
)
from .schemas import BLUEPRINT_INSTANCE_FIELDS, BLUEPRINT_SCHEMA


class Blueprint:
    """Blueprint of a configuration structure."""

    def __init__(
        self,
        data: dict,
        *,
        path: Optional[str] = None,
        expected_domain: Optional[str] = None,
    ) -> None:
        """Initialize a blueprint."""
        try:
            data = self.data = BLUEPRINT_SCHEMA(data)
        except vol.Invalid as err:
            raise InvalidBlueprint(expected_domain, path, data, err) from err

        self.placeholders = placeholder.extract_placeholders(data)

        # In future, we will treat this as "incorrect" and allow to recover from this
        data_domain = data[CONF_BLUEPRINT][CONF_DOMAIN]
        if expected_domain is not None and data_domain != expected_domain:
            raise InvalidBlueprint(
                expected_domain,
                path or self.name,
                data,
                f"Found incorrect blueprint type {data_domain}, expected {expected_domain}",
            )

        self.domain = data_domain

        missing = self.placeholders - set(data[CONF_BLUEPRINT].get(CONF_INPUT, {}))

        if missing:
            raise InvalidBlueprint(
                data_domain,
                path or self.name,
                data,
                f"Missing input definition for {', '.join(missing)}",
            )

    @property
    def name(self) -> str:
        """Return blueprint name."""
        return self.data[CONF_BLUEPRINT][CONF_NAME]

    @property
    def metadata(self) -> dict:
        """Return blueprint metadata."""
        return self.data[CONF_BLUEPRINT]

    def update_metadata(self, *, source_url: Optional[str] = None) -> None:
        """Update metadata."""
        if source_url is not None:
            self.data[CONF_BLUEPRINT][CONF_SOURCE_URL] = source_url


class BlueprintInputs:
    """Inputs for a blueprint."""

    def __init__(
        self, blueprint: Blueprint, config_with_inputs: Dict[str, Any]
    ) -> None:
        """Instantiate a blueprint inputs object."""
        self.blueprint = blueprint
        self.config_with_inputs = config_with_inputs

    @property
    def inputs(self):
        """Return the inputs."""
        return self.config_with_inputs[CONF_USE_BLUEPRINT][CONF_INPUT]

    def validate(self) -> None:
        """Validate the inputs."""
        missing = self.blueprint.placeholders - set(self.inputs)

        if missing:
            raise MissingPlaceholder(
                self.blueprint.domain, self.blueprint.name, missing
            )

        # In future we can see if entities are correct domain, areas exist etc
        # using the new selector helper.

    @callback
    def async_substitute(self) -> dict:
        """Get the blueprint value with the inputs substituted."""
        processed = placeholder.substitute(self.blueprint.data, self.inputs)
        combined = {**self.config_with_inputs, **processed}
        # From config_with_inputs
        combined.pop(CONF_USE_BLUEPRINT)
        # From blueprint
        combined.pop(CONF_BLUEPRINT)
        return combined


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

        hass.data.setdefault(DOMAIN, {})[domain] = self

    @callback
    def async_reset_cache(self) -> None:
        """Reset the blueprint cache."""
        self._blueprints = {}

    def _load_blueprint(self, blueprint_path) -> Blueprint:
        """Load a blueprint."""
        try:
            blueprint_data = yaml.load_yaml(
                self.hass.config.path(BLUEPRINT_FOLDER, self.domain, blueprint_path)
            )
        except (HomeAssistantError, FileNotFoundError) as err:
            raise FailedToLoad(self.domain, blueprint_path, err) from err

        return Blueprint(
            blueprint_data, expected_domain=self.domain, path=blueprint_path
        )

    def _load_blueprints(self) -> Dict[str, Union[Blueprint, BlueprintException]]:
        """Load all the blueprints."""
        blueprint_folder = pathlib.Path(
            self.hass.config.path(BLUEPRINT_FOLDER, self.domain)
        )
        results = {}

        for blueprint_path in blueprint_folder.glob("**/*.yaml"):
            blueprint_path = str(blueprint_path.relative_to(blueprint_folder))
            if self._blueprints.get(blueprint_path) is None:
                try:
                    self._blueprints[blueprint_path] = self._load_blueprint(
                        blueprint_path
                    )
                except BlueprintException as err:
                    self._blueprints[blueprint_path] = None
                    results[blueprint_path] = err
                    continue

            results[blueprint_path] = self._blueprints[blueprint_path]

        return results

    async def async_get_blueprints(
        self,
    ) -> Dict[str, Union[Blueprint, BlueprintException]]:
        """Get all the blueprints."""
        async with self._load_lock:
            return await self.hass.async_add_executor_job(self._load_blueprints)

    async def async_get_blueprint(self, blueprint_path: str) -> Blueprint:
        """Get a blueprint."""
        if blueprint_path in self._blueprints:
            return self._blueprints[blueprint_path]

        async with self._load_lock:
            # Check it again
            if blueprint_path in self._blueprints:
                return self._blueprints[blueprint_path]

            try:
                blueprint = await self.hass.async_add_executor_job(
                    self._load_blueprint, blueprint_path
                )
            except Exception:
                self._blueprints[blueprint_path] = None
                raise

            self._blueprints[blueprint_path] = blueprint
            return blueprint

    async def async_inputs_from_config(
        self, config_with_blueprint: dict
    ) -> BlueprintInputs:
        """Process a blueprint config."""
        try:
            config_with_blueprint = BLUEPRINT_INSTANCE_FIELDS(config_with_blueprint)
        except vol.Invalid as err:
            raise InvalidBlueprintInputs(
                self.domain, humanize_error(config_with_blueprint, err)
            ) from err

        bp_conf = config_with_blueprint[CONF_USE_BLUEPRINT]
        blueprint = await self.async_get_blueprint(bp_conf[CONF_PATH])
        inputs = BlueprintInputs(blueprint, config_with_blueprint)
        inputs.validate()
        return inputs
