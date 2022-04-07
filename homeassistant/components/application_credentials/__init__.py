"""The Application Credentials integration.

This integration provides APIs for managing local OAuth credentials on behalf
of other integrations. Integrations register an authorization server, and then
the APIs are used to add one or more client credentials. Integrations may also
provide credentials from yaml for backwards compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Protocol

import voluptuous as vol

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_DOMAIN, CONF_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection, config_entry_oauth2_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import IntegrationNotFound, async_get_integration
from homeassistant.util import slugify

__all__ = ["ClientCredential", "AuthorizationServer", "async_import_client_credential"]

_LOGGER = logging.getLogger(__name__)

DOMAIN = "application_credentials"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
DATA_STORAGE = "storage"

CREATE_FIELDS = {
    vol.Required(CONF_DOMAIN): cv.string,
    vol.Required(CONF_CLIENT_ID): cv.string,
    vol.Required(CONF_CLIENT_SECRET): cv.string,
}
UPDATE_FIELDS: dict = {}  # Not supported


@dataclass
class ClientCredential:
    """Represent an OAuth client credential."""

    client_id: str
    client_secret: str


@dataclass
class AuthorizationServer:
    """Represent an OAuth2 Authorization Server."""

    authorize_url: str
    token_url: str


class ApplicationCredentialsStorageCollection(collection.StorageCollection):
    """Application credential collection stored in storage."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        result = self.CREATE_SCHEMA(data)
        domain = result[CONF_DOMAIN]
        if not await _get_platform(self.hass, domain):
            raise ValueError("No application_credentials platform for %s" % domain)
        return result

    @callback
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return f"{info[CONF_DOMAIN]}.{info[CONF_CLIENT_ID]}"

    async def _update_data(self, data: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        raise ValueError("Updates not supported")

    async def async_delete_item(self, item_id: str) -> None:
        """Delete item, verifying credential is not in use."""
        if item_id not in self.data:
            raise collection.ItemNotFound(item_id)

        # Cannot delete a credential currently in use by a ConfigEntry
        current = self.data[item_id]
        entries = self.hass.config_entries.async_entries(current[CONF_DOMAIN])
        for entry in entries:
            if entry.data.get("auth_implementation") == item_id:
                raise ValueError("Cannot delete credential in use by an integration")

        await super().async_delete_item(item_id)

    async def async_import_item(self, info: dict) -> None:
        """Import an yaml credential if it does not already exist."""
        suggested_id = self._get_suggested_id(info)
        if self.id_manager.has_id(slugify(suggested_id)):
            return
        await self.async_create_item(info)

    def async_client_credentials(self, domain: str) -> dict[str, ClientCredential]:
        """Return ClientCredentials in storage for the specified domain."""
        credentials = {}
        for item in self.async_items():
            if item[CONF_DOMAIN] != domain:
                continue
            credentials[item[CONF_ID]] = ClientCredential(
                item[CONF_CLIENT_ID], item[CONF_CLIENT_SECRET]
            )
        return credentials


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Application Credentials."""
    hass.data[DOMAIN] = {}

    id_manager = collection.IDManager()
    storage_collection = ApplicationCredentialsStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        logging.getLogger(f"{__name__}.storage_collection"),
        id_manager,
    )
    await storage_collection.async_load()
    hass.data[DOMAIN][DATA_STORAGE] = storage_collection

    collection.StorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    config_entry_oauth2_flow.async_add_implementation_provider(
        hass, DOMAIN, _async_provide_implementation
    )

    return True


async def async_import_client_credential(
    hass: HomeAssistant, domain: str, credential: ClientCredential
) -> None:
    """Import an existing credential from configuration.yaml."""
    if DOMAIN not in hass.data:
        raise ValueError("Integration 'application_credentials' not setup")
    storage_collection = hass.data[DOMAIN][DATA_STORAGE]
    item = {
        CONF_DOMAIN: domain,
        CONF_CLIENT_ID: credential.client_id,
        CONF_CLIENT_SECRET: credential.client_secret,
    }
    await storage_collection.async_import_item(item)


async def _async_provide_implementation(
    hass: HomeAssistant, domain: str
) -> list[config_entry_oauth2_flow.AbstractOAuth2Implementation]:
    """Return registered OAuth implementations."""

    platform = await _get_platform(hass, domain)
    if not platform:
        return []

    authorization_server = await platform.async_get_authorization_server(hass)
    storage_collection = hass.data[DOMAIN][DATA_STORAGE]
    credentials = storage_collection.async_client_credentials(domain)
    return [
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            auth_domain,
            credential.client_id,
            credential.client_secret,
            authorization_server.authorize_url,
            authorization_server.token_url,
        )
        for auth_domain, credential in credentials.items()
    ]


class ApplicationCredentialsProtocol(Protocol):
    """Define the format that application_credentials platforms can have."""

    async def async_get_authorization_server(
        self, hass: HomeAssistant
    ) -> AuthorizationServer:
        """Return authorization server."""


async def _get_platform(
    hass: HomeAssistant, integration_domain: str
) -> ApplicationCredentialsProtocol | None:
    """Register an application_credentials platform."""
    try:
        integration = await async_get_integration(hass, integration_domain)
    except IntegrationNotFound as err:
        _LOGGER.debug("Integration '%s' does not exist: %s", integration_domain, err)
        return None
    try:
        platform = integration.get_platform("application_credentials")
    except ImportError as err:
        _LOGGER.debug(
            "Integration '%s' does not provide application_credentials: %s",
            integration_domain,
            err,
        )
        return None
    if not hasattr(platform, "async_get_authorization_server"):
        raise ValueError(
            "Integration '%s' platform application_credentials did not implement 'async_get_authorization_server'"
        )
    return platform
