"""Config flow for GPM integration."""

from __future__ import annotations

import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TYPE, CONF_URL
from homeassistant.data_entry_flow import AbortFlow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from . import get_manager
from ._manager import (
    AlreadyClonedError,
    GPMError,
    InvalidStructure,
    RepositoryManager,
    RepositoryType,
    ResourceRepositoryManager,
    UpdateStrategy,
)
from .const import CONF_DOWNLOAD_URL, CONF_UPDATE_STRATEGY, DOMAIN

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
        vol.Required(CONF_DOWNLOAD_URL): str,
    }
)


class GPMConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GPM."""

    VERSION = 1
    _user_input: dict[str, str]
    manager: RepositoryManager

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                cv.url(user_input[CONF_URL])
                self._user_input = {
                    CONF_URL: user_input[CONF_URL],
                    CONF_TYPE: user_input[CONF_TYPE],
                    CONF_UPDATE_STRATEGY: user_input[CONF_UPDATE_STRATEGY],
                }
                self.manager = get_manager(self.hass, user_input)
                await self.async_set_unique_id(self.manager.unique_id)
                self._abort_if_unique_id_configured()
                if user_input[CONF_TYPE] == RepositoryType.RESOURCE:
                    return await self.async_step_resource()
                return await self.async_step_install()
            except AbortFlow:
                raise
            except vol.Invalid:
                _LOGGER.exception("Invalid url")
                errors[CONF_URL] = "invalid_url"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        data_schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA, user_input or {}
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_resource(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the resource step."""
        errors: dict[str, str] = {}
        assert self._user_input is not None
        assert self._user_input[CONF_TYPE] == RepositoryType.RESOURCE
        manager = cast(ResourceRepositoryManager, self.manager)
        if user_input is not None:
            try:
                download_url = cv.template(user_input[CONF_DOWNLOAD_URL])
                manager.set_download_url(download_url)
                self._user_input[CONF_DOWNLOAD_URL] = user_input[CONF_DOWNLOAD_URL]
                return await self.async_step_install()
            except vol.Invalid:
                _LOGGER.exception("Invalid template")
                errors[CONF_DOWNLOAD_URL] = "invalid_template"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        data_schema = self.add_suggested_values_to_schema(
            STEP_RESOURCE_DATA_SCHEMA, user_input or {}
        )
        return self.async_show_form(
            step_id="resource", data_schema=data_schema, errors=errors
        )

    async def async_step_install(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the install step."""
        abort_reason = None
        assert self._user_input is not None

        try:
            await self.manager.clone()
            latest_version = await self.manager.get_latest_version()
            await self.manager.checkout(latest_version)
            await self.manager.install()
            title = await self.manager.get_title()
            return self.async_create_entry(
                title=title,
                data=self._user_input,
            )

        except InvalidStructure:
            _LOGGER.exception("Invalid structure")
            abort_reason = "invalid_structure"
            await self.manager.remove()
        except AlreadyClonedError:
            _LOGGER.exception("Installation failed")
            abort_reason = "install_failed"
        except GPMError:
            _LOGGER.exception("Installation failed")
            abort_reason = "install_failed"
            await self.manager.remove()
        except Exception:
            _LOGGER.exception("Unexpected exception")
            abort_reason = "unknown"

        return self.async_abort(
            reason=abort_reason,
        )
