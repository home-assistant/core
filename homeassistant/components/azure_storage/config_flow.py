"""Config flow for Azure Storage integration."""

from collections.abc import Mapping
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

    async def get_container_client(
        self, account_name: str, container_name: str, storage_account_key: str
    ) -> ContainerClient:
        """Get the container client.

        ContainerClient has a blocking call to open in cpython
        """

        session = async_get_clientsession(self.hass)

        def create_container_client() -> ContainerClient:
            return ContainerClient(
                account_url=f"https://{account_name}.blob.core.windows.net/",
                container_name=container_name,
                credential=storage_account_key,
                transport=AioHttpTransport(session=session),
            )

        return await self.hass.async_add_executor_job(create_container_client)

    async def validate_config(
        self, container_client: ContainerClient
    ) -> dict[str, str]:
        """Validate the configuration."""
        errors: dict[str, str] = {}
        try:
            await container_client.exists()
        except ResourceNotFoundError:
            errors["base"] = "cannot_connect"
        except ClientAuthenticationError:
            errors[CONF_STORAGE_ACCOUNT_KEY] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unknown exception occurred")
            errors["base"] = "unknown"
        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User step for Azure Storage."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_ACCOUNT_NAME: user_input[CONF_ACCOUNT_NAME]}
            )
            container_client = await self.get_container_client(
                account_name=user_input[CONF_ACCOUNT_NAME],
                container_name=user_input[CONF_CONTAINER_NAME],
                storage_account_key=user_input[CONF_STORAGE_ACCOUNT_KEY],
            )
            errors = await self.validate_config(container_client)

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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            container_client = await self.get_container_client(
                account_name=reauth_entry.data[CONF_ACCOUNT_NAME],
                container_name=reauth_entry.data[CONF_CONTAINER_NAME],
                storage_account_key=user_input[CONF_STORAGE_ACCOUNT_KEY],
            )

            errors = await self.validate_config(container_client)
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={**reauth_entry.data, **user_input},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STORAGE_ACCOUNT_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure the entry."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            container_client = await self.get_container_client(
                account_name=reconfigure_entry.data[CONF_ACCOUNT_NAME],
                container_name=user_input[CONF_CONTAINER_NAME],
                storage_account_key=user_input[CONF_STORAGE_ACCOUNT_KEY],
            )
            errors = await self.validate_config(container_client)
            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={**reconfigure_entry.data, **user_input},
                )
        return self.async_show_form(
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CONTAINER_NAME,
                        default=reconfigure_entry.data[CONF_CONTAINER_NAME],
                    ): str,
                    vol.Required(
                        CONF_STORAGE_ACCOUNT_KEY,
                        default=reconfigure_entry.data[CONF_STORAGE_ACCOUNT_KEY],
                    ): str,
                }
            ),
            errors=errors,
        )
