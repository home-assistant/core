"""Blueprint models."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
import pathlib
import shutil
from typing import Any

from awesomeversion import AwesomeVersion
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant import loader
from homeassistant.const import (
    CONF_DEFAULT,
    CONF_DOMAIN,
    CONF_NAME,
    CONF_PATH,
    __version__,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import yaml

from .const import (
    BLUEPRINT_FOLDER,
    CONF_BLUEPRINT,
    CONF_HOMEASSISTANT,
    CONF_INPUT,
    CONF_MIN_VERSION,
    CONF_SOURCE_URL,
    CONF_USE_BLUEPRINT,
    DOMAIN,
)
from .errors import (
    BlueprintException,
    BlueprintInUse,
    FailedToLoad,
    FileAlreadyExists,
    InvalidBlueprint,
    InvalidBlueprintInputs,
    MissingInput,
)
from .schemas import BLUEPRINT_INSTANCE_FIELDS, BLUEPRINT_SCHEMA


class Blueprint:
    """Blueprint of a configuration structure."""

    def __init__(
        self,
        data: dict[str, Any],
        *,
        path: str | None = None,
        expected_domain: str | None = None,
    ) -> None:
        """Initialize a blueprint."""
        try:
            data = self.data = BLUEPRINT_SCHEMA(data)
        except vol.Invalid as err:
            raise InvalidBlueprint(expected_domain, path, data, err) from err

        # In future, we will treat this as "incorrect" and allow to recover from this
        data_domain = data[CONF_BLUEPRINT][CONF_DOMAIN]
        if expected_domain is not None and data_domain != expected_domain:
            raise InvalidBlueprint(
                expected_domain,
                path or self.name,
                data,
                (
                    f"Found incorrect blueprint type {data_domain}, expected"
                    f" {expected_domain}"
                ),
            )

        self.domain = data_domain

        missing = yaml.extract_inputs(data) - set(data[CONF_BLUEPRINT][CONF_INPUT])

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
        return self.data[CONF_BLUEPRINT][CONF_NAME]  # type: ignore[no-any-return]

    @property
    def inputs(self) -> dict[str, Any]:
        """Return blueprint inputs."""
        return self.data[CONF_BLUEPRINT][CONF_INPUT]  # type: ignore[no-any-return]

    @property
    def metadata(self) -> dict[str, Any]:
        """Return blueprint metadata."""
        return self.data[CONF_BLUEPRINT]  # type: ignore[no-any-return]

    def update_metadata(self, *, source_url: str | None = None) -> None:
        """Update metadata."""
        if source_url is not None:
            self.data[CONF_BLUEPRINT][CONF_SOURCE_URL] = source_url

    def yaml(self) -> str:
        """Dump blueprint as YAML."""
        return yaml.dump(self.data)

    @callback
    def validate(self) -> list[str] | None:
        """Test if the Home Assistant installation supports this blueprint.

        Return list of errors if not valid.
        """
        errors = []
        metadata = self.metadata
        min_version = metadata.get(CONF_HOMEASSISTANT, {}).get(CONF_MIN_VERSION)

        if min_version is not None and AwesomeVersion(__version__) < AwesomeVersion(
            min_version
        ):
            errors.append(f"Requires at least Home Assistant {min_version}")

        return errors or None


class BlueprintInputs:
    """Inputs for a blueprint."""

    def __init__(
        self, blueprint: Blueprint, config_with_inputs: dict[str, Any]
    ) -> None:
        """Instantiate a blueprint inputs object."""
        self.blueprint = blueprint
        self.config_with_inputs = config_with_inputs

    @property
    def inputs(self) -> dict[str, Any]:
        """Return the inputs."""
        return self.config_with_inputs[CONF_USE_BLUEPRINT][CONF_INPUT]  # type: ignore[no-any-return]

    @property
    def inputs_with_default(self) -> dict[str, Any]:
        """Return the inputs and fallback to defaults."""
        no_input = set(self.blueprint.inputs) - set(self.inputs)

        inputs_with_default = dict(self.inputs)

        for inp in no_input:
            blueprint_input = self.blueprint.inputs[inp]
            if isinstance(blueprint_input, dict) and CONF_DEFAULT in blueprint_input:
                inputs_with_default[inp] = blueprint_input[CONF_DEFAULT]

        return inputs_with_default

    def validate(self) -> None:
        """Validate the inputs."""
        missing = set(self.blueprint.inputs) - set(self.inputs_with_default)

        if missing:
            raise MissingInput(self.blueprint.domain, self.blueprint.name, missing)

        # In future we can see if entities are correct domain, areas exist etc
        # using the new selector helper.

    @callback
    def async_substitute(self) -> dict:
        """Get the blueprint value with the inputs substituted."""
        processed = yaml.substitute(self.blueprint.data, self.inputs_with_default)
        combined = {**processed, **self.config_with_inputs}
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
        blueprint_in_use: Callable[[HomeAssistant, str], bool],
        reload_blueprint_consumers: Callable[[HomeAssistant, str], Awaitable[None]],
    ) -> None:
        """Initialize a domain blueprints instance."""
        self.hass = hass
        self.domain = domain
        self.logger = logger
        self._blueprint_in_use = blueprint_in_use
        self._reload_blueprint_consumers = reload_blueprint_consumers
        self._blueprints: dict[str, Blueprint | None] = {}
        self._load_lock = asyncio.Lock()

        hass.data.setdefault(DOMAIN, {})[domain] = self

    @property
    def blueprint_folder(self) -> pathlib.Path:
        """Return the blueprint folder."""
        return pathlib.Path(self.hass.config.path(BLUEPRINT_FOLDER, self.domain))

    async def async_reset_cache(self) -> None:
        """Reset the blueprint cache."""
        async with self._load_lock:
            self._blueprints = {}

    def _load_blueprint(self, blueprint_path: str) -> Blueprint:
        """Load a blueprint."""
        try:
            blueprint_data = yaml.load_yaml_dict(self.blueprint_folder / blueprint_path)
        except FileNotFoundError as err:
            raise FailedToLoad(
                self.domain,
                blueprint_path,
                FileNotFoundError(f"Unable to find {blueprint_path}"),
            ) from err
        except HomeAssistantError as err:
            raise FailedToLoad(self.domain, blueprint_path, err) from err

        return Blueprint(
            blueprint_data, expected_domain=self.domain, path=blueprint_path
        )

    def _load_blueprints(self) -> dict[str, Blueprint | BlueprintException | None]:
        """Load all the blueprints."""
        blueprint_folder = pathlib.Path(
            self.hass.config.path(BLUEPRINT_FOLDER, self.domain)
        )
        results: dict[str, Blueprint | BlueprintException | None] = {}

        for path in blueprint_folder.glob("**/*.yaml"):
            blueprint_path = str(path.relative_to(blueprint_folder))
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
    ) -> dict[str, Blueprint | BlueprintException | None]:
        """Get all the blueprints."""
        async with self._load_lock:
            return await self.hass.async_add_executor_job(self._load_blueprints)

    async def async_get_blueprint(self, blueprint_path: str) -> Blueprint:
        """Get a blueprint."""

        def load_from_cache() -> Blueprint:
            """Load blueprint from cache."""
            if (blueprint := self._blueprints[blueprint_path]) is None:
                raise FailedToLoad(
                    self.domain,
                    blueprint_path,
                    FileNotFoundError(f"Unable to find {blueprint_path}"),
                )
            return blueprint

        if blueprint_path in self._blueprints:
            return load_from_cache()

        async with self._load_lock:
            # Check it again
            if blueprint_path in self._blueprints:
                return load_from_cache()

            try:
                blueprint = await self.hass.async_add_executor_job(
                    self._load_blueprint, blueprint_path
                )
            except FailedToLoad:
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

    async def async_remove_blueprint(self, blueprint_path: str) -> None:
        """Remove a blueprint file."""
        if self._blueprint_in_use(self.hass, blueprint_path):
            raise BlueprintInUse(self.domain, blueprint_path)
        path = self.blueprint_folder / blueprint_path
        await self.hass.async_add_executor_job(path.unlink)
        self._blueprints[blueprint_path] = None

    def _create_file(
        self, blueprint: Blueprint, blueprint_path: str, allow_override: bool
    ) -> bool:
        """Create blueprint file.

        Returns true if the action overrides an existing blueprint.
        """

        path = pathlib.Path(
            self.hass.config.path(BLUEPRINT_FOLDER, self.domain, blueprint_path)
        )
        exists = path.exists()

        if not allow_override and exists:
            raise FileAlreadyExists(self.domain, blueprint_path)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(blueprint.yaml(), encoding="utf-8")
        return exists

    async def async_add_blueprint(
        self, blueprint: Blueprint, blueprint_path: str, allow_override: bool = False
    ) -> bool:
        """Add a blueprint."""
        overrides_existing = await self.hass.async_add_executor_job(
            self._create_file, blueprint, blueprint_path, allow_override
        )

        self._blueprints[blueprint_path] = blueprint

        if overrides_existing:
            await self._reload_blueprint_consumers(self.hass, blueprint_path)

        return overrides_existing

    async def async_populate(self) -> None:
        """Create folder if it doesn't exist and populate with examples."""
        if self._blueprints:
            # If we have already loaded some blueprint the blueprint folder must exist
            return

        integration = await loader.async_get_integration(self.hass, self.domain)

        def populate() -> None:
            if self.blueprint_folder.exists():
                return

            shutil.copytree(
                integration.file_path / BLUEPRINT_FOLDER,
                self.blueprint_folder / HA_DOMAIN,
            )

        await self.hass.async_add_executor_job(populate)
