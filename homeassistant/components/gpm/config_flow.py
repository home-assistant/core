"""Config flow for GPM integration."""

from __future__ import annotations

import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TYPE, CONF_URL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import async_create_issue
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from . import get_manager
from ._manager import (
    GPMError,
    IntegrationRepositoryManager,
    InvalidStructure,
    RepositoryManager,
    RepositoryType,
    UpdateStrategy,
)
from .const import CONF_UPDATE_STRATEGY, DOMAIN
from .repairs import create_restart_issue

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TYPE, default=RepositoryType.INTEGRATION): SelectSelector(
            SelectSelectorConfig(
                options=list(map(str, RepositoryType)),
                translation_key=CONF_TYPE,
            )
        ),
        vol.Required(
            CONF_UPDATE_STRATEGY, default=UpdateStrategy.LATEST_TAG
        ): SelectSelector(
            SelectSelectorConfig(
                options=list(map(str, UpdateStrategy)),
                translation_key=CONF_UPDATE_STRATEGY,
            )
        ),
    }
)

STEP_RESOURCE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.template,
    }
)


class GPMConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GPM."""

    VERSION = 1
    _step_user_data: dict[str, str]
    manager: RepositoryManager

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.manager = get_manager(self.hass, user_input)
            await self.async_set_unique_id(self.manager.slug)
            self._abort_if_unique_id_configured()
            try:
                await self.hass.async_add_executor_job(self.manager.clone)
                latest_version = await self.hass.async_add_executor_job(
                    self.manager.get_latest_version
                )
                await self.hass.async_add_executor_job(
                    self.manager.checkout, latest_version
                )
                await self.hass.async_add_executor_job(self.manager.install)
            except InvalidStructure:
                _LOGGER.exception("Invalid structure")
                errors["base"] = "invalid_structure"
                await self.hass.async_add_executor_job(self.manager.remove)
            except GPMError:
                _LOGGER.exception("Installation failed")
                errors["base"] = "install_failed"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._step_user_data = {
                    CONF_URL: user_input[CONF_URL],
                    CONF_TYPE: user_input[CONF_TYPE],
                    CONF_UPDATE_STRATEGY: user_input[CONF_UPDATE_STRATEGY],
                }
                if user_input[CONF_TYPE] == RepositoryType.INTEGRATION:
                    manager = cast(IntegrationRepositoryManager, self.manager)
                    create_restart_issue(
                        async_create_issue,
                        self.hass,
                        action="install",
                        name=manager.component_name,
                    )
                    return self.async_create_entry(
                        title=manager.component_name,
                        data=self._step_user_data,
                    )
                if user_input[CONF_TYPE] == RepositoryType.RESOURCE:
                    return await self.async_step_resource()

        data_schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA, user_input or {}
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_resource(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        assert self._step_user_data is not None
        if user_input is not None:
            user_input = {**self._step_user_data, **user_input}
            raise NotImplementedError

        return self.async_show_form(
            step_id="resource", data_schema=STEP_RESOURCE_DATA_SCHEMA, errors=errors
        )
