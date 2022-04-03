"""The Application Credentials integration.

This integration provides APIs for managing local OAuth credentials on behalf of other
integrations. The preferred approach for all OAuth integrations is to use the cloud
account linking service, and this is the alternative for integrations that can't use
it.

Integrations register an authorization server, and then the APIs are used to add
add one or more client credentials. Integrations may also provide credentials
from yaml for backwards compatibility.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Protocol

import voluptuous as vol

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    collection,
    config_entry_oauth2_flow,
    integration_platform,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .const import DOMAIN, ApplicationCredentialsType

__all__ = ["ClientCredential", "AuthorizationServer"]

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

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
        authorization_server = await _async_get_authorization_server(self.hass, domain)
        if not authorization_server:
            raise ValueError("No authorization server registered for %s" % domain)
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


class ApplicationCredentialsStorageListener:
    """Listener that handles registering and unregistering OAuth implementations for credentials."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize ApplicationCredentialsStorageListener."""
        self.hass = hass

    async def updated(self, change_type: str, item_id: str, config: dict):
        """Update set of registered authentication implementations."""
        if change_type not in [collection.CHANGE_ADDED, collection.CHANGE_REMOVED]:
            # not expected
            return
        integration_domain = config[CONF_DOMAIN]
        credential = ClientCredential(
            config[CONF_CLIENT_ID], config[CONF_CLIENT_SECRET]
        )
        if change_type == collection.CHANGE_REMOVED:
            _async_unregister_auth_implementation(
                self.hass, integration_domain, credential
            )
        else:
            await _async_register_auth_implementation(
                self.hass, integration_domain, credential
            )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Application Credentials."""
    hass.data[DOMAIN] = {}

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _register_application_credentials_platform
    )

    # Credentials from storage
    id_manager = collection.IDManager()
    storage_collection = ApplicationCredentialsStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        logging.getLogger(f"{__name__}.storage_collection"),
        id_manager,
    )
    storage_listener = ApplicationCredentialsStorageListener(hass)
    storage_collection.async_add_listener(storage_listener.updated)
    await storage_collection.async_load()

    collection.StorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    # Allow future registration of local oauth implementations
    config_entry_oauth2_flow.async_register_local_apis(hass)

    return True


# Creates AbstractOAuth2Implementation given a ClientCredential for a specific domain
AuthImplFactory = Callable[
    [str, ClientCredential], config_entry_oauth2_flow.AbstractOAuth2Implementation
]


def _get_auth_domain(domain: str, credential: ClientCredential) -> str:
    """Return the OAuth2 flow implementation domain."""
    return slugify(f"{domain}.{credential.client_id}")


async def _async_register_auth_implementation(
    hass: HomeAssistant,
    domain: str,
    credential: ClientCredential,
) -> None:
    """Register an OAuth2 flow implementation for an integration."""
    auth_domain = _get_auth_domain(domain, credential)
    if auth_domain in hass.data[DOMAIN][domain]:
        raise ValueError(f"Domain {auth_domain} already registered")
    authorization_server = await _async_get_authorization_server(hass, domain)
    if not authorization_server:
        raise ValueError("No authorization server registered for %s" % domain)
    auth_impl = config_entry_oauth2_flow.LocalOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        credential.client_secret,
        authorization_server.authorize_url,
        authorization_server.token_url,
    )
    unsub = config_entry_oauth2_flow.async_register_implementation(
        hass, domain, auth_impl
    )
    hass.data[DOMAIN][domain][auth_domain] = unsub


def _async_unregister_auth_implementation(
    hass: HomeAssistant, domain: str, credential: ClientCredential
) -> None:
    """Register an OAuth2 flow implementation for an integration."""
    auth_domain = _get_auth_domain(domain, credential)
    unsub = hass.data[DOMAIN][domain].pop(auth_domain)
    unsub()


async def _async_get_authorization_server(
    hass: HomeAssistant, domain: str
) -> AuthorizationServer | None:
    """Return the AuthorizationServer for the integration domain."""
    if domain not in hass.data[DOMAIN]:
        return None
    get_authorization_server = hass.data[DOMAIN][domain][
        ApplicationCredentialsType.AUTHORIZATION_SERVER.value
    ]
    authorization_server = await get_authorization_server(hass)
    if not authorization_server:
        return None
    return authorization_server


class ApplicationCredentialsProtocol(Protocol):
    """Define the format that application_credentials platforms can have."""

    async def async_get_authorization_server(
        self, hass: HomeAssistant
    ) -> AuthorizationServer:
        """Return authorization server."""

    async def async_get_client_credential(
        self, hass: HomeAssistant
    ) -> ClientCredential:
        """Return a client credential from configuration.yaml."""


async def _register_application_credentials_platform(
    hass: HomeAssistant,
    integration_domain: str,
    platform: ApplicationCredentialsProtocol,
):
    """Register an application_credentials platform."""
    get_authorization_server = getattr(platform, "async_get_authorization_server", None)
    if get_authorization_server is None:
        return
    get_config_client_credential = getattr(
        platform, "async_get_client_credential", None
    )
    hass.data[DOMAIN][integration_domain] = {
        ApplicationCredentialsType.AUTHORIZATION_SERVER.value: get_authorization_server,
        ApplicationCredentialsType.CONFIG_CREDENTIAL.value: get_config_client_credential,
    }
    # Register an authentication implementation for every credential provided
    if get_config_client_credential is None:
        return
    credential = await get_config_client_credential(hass)
    if not credential:
        return
    await _async_register_auth_implementation(hass, integration_domain, credential)
