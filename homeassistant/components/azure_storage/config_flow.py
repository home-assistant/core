"""Config flow for Azure Storage integration."""

import logging
from typing import Any

from azure.core.exceptions import ClientAuthenticationError, ResourceNotFoundError
from azure.core.pipeline.transport._aiohttp import (
    AioHttpTransport,
)  # need to import from private file, as it is not properly imported in the init
from azure.storage.blob.aio import ContainerClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ACCOUNT_NAME,
    CONF_CONTAINER_NAME,
    CONF_STORAGE_ACCOUNT_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class AzureStorageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for azure storage."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User step for Azure Storage."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_ACCOUNT_NAME: user_input[CONF_ACCOUNT_NAME]}
            )
            container_client = ContainerClient(
                account_url=f"https://{user_input[CONF_ACCOUNT_NAME]}.blob.core.windows.net/",
                container_name=user_input[CONF_CONTAINER_NAME],
                credential=user_input[CONF_STORAGE_ACCOUNT_KEY],
                transport=AioHttpTransport(session=async_get_clientsession(self.hass)),
            )
            try:
                await container_client.exists()
            except ResourceNotFoundError:
                errors["base"] = "cannot_connect"
            except ClientAuthenticationError:
                errors[CONF_STORAGE_ACCOUNT_KEY] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unknown exception occurred")
                errors["base"] = "unknown"
            if not errors:
                return self.async_create_entry(
                    title=f"{user_input[CONF_ACCOUNT_NAME]}/{user_input[CONF_CONTAINER_NAME]}",
                    data=user_input,
                )

        return self.async_show_form(
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCOUNT_NAME): str,
                    vol.Required(
                        CONF_CONTAINER_NAME, default="home-assistant-backups"
                    ): str,
                    vol.Required(CONF_STORAGE_ACCOUNT_KEY): str,
                }
            ),
            errors=errors,
        )
