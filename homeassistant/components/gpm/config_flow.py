"""Config flow for GPM integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TYPE, CONF_URL
from homeassistant.helpers.issue_registry import async_create_issue
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from ._manager import GPMError, RepositoryManager, RepositoryType, UpdateStrategy
from .const import (
    CONF_UPDATE_STRATEGY,
    DOMAIN,
    PATH_CLONE_BASEDIR,
    PATH_INSTALL_BASEDIR,
)
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


class GPMConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GPM."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            manager = RepositoryManager(
                user_input[CONF_URL],
                RepositoryType(user_input[CONF_TYPE]),
                self.hass.config.path(PATH_CLONE_BASEDIR),
                self.hass.config.path(PATH_INSTALL_BASEDIR),
                UpdateStrategy(user_input[CONF_UPDATE_STRATEGY]),
            )
            await self.async_set_unique_id(manager.slug)
            self._abort_if_unique_id_configured()
            try:
                await self.hass.async_add_executor_job(manager.clone)
                latest_version = await self.hass.async_add_executor_job(
                    manager.get_latest_version
                )
                await self.hass.async_add_executor_job(manager.checkout, latest_version)
                await self.hass.async_add_executor_job(manager.install)
            except GPMError:
                _LOGGER.exception("Installation failed")
                errors["base"] = "install_failed"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                create_restart_issue(
                    async_create_issue,
                    self.hass,
                    action="install",
                    component_name=manager.component_name,
                )
                return self.async_create_entry(
                    title=manager.slug,
                    data={
                        CONF_URL: user_input[CONF_URL],
                        CONF_TYPE: user_input[CONF_TYPE],
                        CONF_UPDATE_STRATEGY: user_input[CONF_UPDATE_STRATEGY],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
