"""Pluggable auth modules for Home Assistant."""
from __future__ import annotations

import importlib
import logging
import types
from typing import Any

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant import data_entry_flow, requirements
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.decorator import Registry

MULTI_FACTOR_AUTH_MODULES: Registry[str, type[MultiFactorAuthModule]] = Registry()

MULTI_FACTOR_AUTH_MODULE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE): str,
        vol.Optional(CONF_NAME): str,
        # Specify ID if you have two mfa auth module for same type.
        vol.Optional(CONF_ID): str,
    },
    extra=vol.ALLOW_EXTRA,
)

DATA_REQS = "mfa_auth_module_reqs_processed"

_LOGGER = logging.getLogger(__name__)


class MultiFactorAuthModule:
    """Multi-factor Auth Module of validation function."""

    DEFAULT_TITLE = "Unnamed auth module"
    MAX_RETRY_TIME = 3

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize an auth module."""
        self.hass = hass
        self.config = config

    @property
    def id(self) -> str:
        """Return id of the auth module.

        Default is same as type
        """
        return self.config.get(CONF_ID, self.type)

    @property
    def type(self) -> str:
        """Return type of the module."""
        return self.config[CONF_TYPE]  # type: ignore[no-any-return]

    @property
    def name(self) -> str:
        """Return the name of the auth module."""
        return self.config.get(CONF_NAME, self.DEFAULT_TITLE)

    # Implement by extending class

    @property
    def input_schema(self) -> vol.Schema:
        """Return a voluptuous schema to define mfa auth module's input."""
        raise NotImplementedError

    async def async_setup_flow(self, user_id: str) -> SetupFlow:
        """Return a data entry flow handler for setup module.

        Mfa module should extend SetupFlow
        """
        raise NotImplementedError

    async def async_setup_user(self, user_id: str, setup_data: Any) -> Any:
        """Set up user for mfa auth module."""
        raise NotImplementedError

    async def async_depose_user(self, user_id: str) -> None:
        """Remove user from mfa module."""
        raise NotImplementedError

    async def async_is_user_setup(self, user_id: str) -> bool:
        """Return whether user is setup."""
        raise NotImplementedError

    async def async_validate(self, user_id: str, user_input: dict[str, Any]) -> bool:
        """Return True if validation passed."""
        raise NotImplementedError


class SetupFlow(data_entry_flow.FlowHandler):
    """Handler for the setup flow."""

    def __init__(
        self, auth_module: MultiFactorAuthModule, setup_schema: vol.Schema, user_id: str
    ) -> None:
        """Initialize the setup flow."""
        self._auth_module = auth_module
        self._setup_schema = setup_schema
        self._user_id = user_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of setup flow.

        Return self.async_show_form(step_id='init') if user_input is None.
        Return self.async_create_entry(data={'result': result}) if finish.
        """
        errors: dict[str, str] = {}

        if user_input:
            result = await self._auth_module.async_setup_user(self._user_id, user_input)
            return self.async_create_entry(
                title=self._auth_module.name, data={"result": result}
            )

        return self.async_show_form(
            step_id="init", data_schema=self._setup_schema, errors=errors
        )


async def auth_mfa_module_from_config(
    hass: HomeAssistant, config: dict[str, Any]
) -> MultiFactorAuthModule:
    """Initialize an auth module from a config."""
    module_name: str = config[CONF_TYPE]
    module = await _load_mfa_module(hass, module_name)

    try:
        config = module.CONFIG_SCHEMA(config)
    except vol.Invalid as err:
        _LOGGER.error(
            "Invalid configuration for multi-factor module %s: %s",
            module_name,
            humanize_error(config, err),
        )
        raise

    return MULTI_FACTOR_AUTH_MODULES[module_name](hass, config)


async def _load_mfa_module(hass: HomeAssistant, module_name: str) -> types.ModuleType:
    """Load an mfa auth module."""
    module_path = f"homeassistant.auth.mfa_modules.{module_name}"

    try:
        module = importlib.import_module(module_path)
    except ImportError as err:
        _LOGGER.error("Unable to load mfa module %s: %s", module_name, err)
        raise HomeAssistantError(
            f"Unable to load mfa module {module_name}: {err}"
        ) from err

    if hass.config.skip_pip or not hasattr(module, "REQUIREMENTS"):
        return module

    processed = hass.data.get(DATA_REQS)
    if processed and module_name in processed:
        return module

    processed = hass.data[DATA_REQS] = set()

    await requirements.async_process_requirements(
        hass, module_path, module.REQUIREMENTS
    )

    processed.add(module_name)
    return module
