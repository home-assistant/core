"""The Application Credentials integration.

This integration provides APIs for managing local OAuth credentials on behalf
of other integrations. Integrations register an authorization server, and then
the APIs are used to add one or more client credentials. Integrations may also
provide credentials from yaml for backwards compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Protocol

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DOMAIN,
    CONF_ID,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    collection,
    config_entry_oauth2_flow,
    config_validation as cv,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType
from homeassistant.loader import (
    IntegrationNotFound,
    async_get_application_credentials,
    async_get_integration,
)
from homeassistant.util import slugify
from homeassistant.util.hass_dict import HassKey

__all__ = ["AuthorizationServer", "ClientCredential", "async_import_client_credential"]

_LOGGER = logging.getLogger(__name__)

DOMAIN = "application_credentials"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
DATA_COMPONENT: HassKey[ApplicationCredentialsStorageCollection] = HassKey(DOMAIN)
CONF_AUTH_DOMAIN = "auth_domain"
DEFAULT_IMPORT_NAME = "Import from configuration.yaml"

CREATE_FIELDS: VolDictType = {
    vol.Required(CONF_DOMAIN): cv.string,
    vol.Required(CONF_CLIENT_ID): vol.All(cv.string, vol.Strip),
    vol.Required(CONF_CLIENT_SECRET): vol.All(cv.string, vol.Strip),
    vol.Optional(CONF_AUTH_DOMAIN): cv.string,
    vol.Optional(CONF_NAME): cv.string,
}
UPDATE_FIELDS: VolDictType = {}  # Not supported

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@dataclass
class ClientCredential:
    """Represent an OAuth client credential."""

    client_id: str
    client_secret: str
    name: str | None = None


@dataclass
class AuthorizationServer:
    """Represent an OAuth2 Authorization Server."""

    authorize_url: str
    token_url: str


class ApplicationCredentialsStorageCollection(collection.DictStorageCollection):
    """Application credential collection stored in storage."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)

    async def _process_create_data(self, data: dict[str, str]) -> dict[str, str]:
        """Validate the config is valid."""
        result = self.CREATE_SCHEMA(data)
        domain = result[CONF_DOMAIN]
        if not await _get_platform(self.hass, domain):
            raise ValueError(f"No application_credentials platform for {domain}")
        return result

    @callback
    def _get_suggested_id(self, info: dict[str, str]) -> str:
        """Suggest an ID based on the config."""
        return f"{info[CONF_DOMAIN]}.{info[CONF_CLIENT_ID]}"

    async def _update_data(
        self, item: dict[str, str], update_data: dict[str, str]
    ) -> dict[str, str]:
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
                raise HomeAssistantError(
                    f"Cannot delete credential in use by integration {entry.domain}"
                )

        await super().async_delete_item(item_id)

    async def async_import_item(self, info: dict[str, str]) -> None:
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
            auth_domain = item.get(CONF_AUTH_DOMAIN, item[CONF_ID])
            credentials[auth_domain] = ClientCredential(
                client_id=item[CONF_CLIENT_ID],
                client_secret=item[CONF_CLIENT_SECRET],
                name=item.get(CONF_NAME),
            )
        return credentials


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Application Credentials."""
    id_manager = collection.IDManager()
    storage_collection = ApplicationCredentialsStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    await storage_collection.async_load()
    hass.data[DATA_COMPONENT] = storage_collection

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    websocket_api.async_register_command(hass, handle_integration_list)
    websocket_api.async_register_command(hass, handle_config_entry)

    config_entry_oauth2_flow.async_add_implementation_provider(
        hass, DOMAIN, _async_provide_implementation
    )

    return True


async def async_import_client_credential(
    hass: HomeAssistant,
    domain: str,
    credential: ClientCredential,
    auth_domain: str | None = None,
) -> None:
    """Import an existing credential from configuration.yaml."""
    if DOMAIN not in hass.data:
        raise ValueError("Integration 'application_credentials' not setup")
    item = {
        CONF_DOMAIN: domain,
        CONF_CLIENT_ID: credential.client_id,
        CONF_CLIENT_SECRET: credential.client_secret,
        CONF_AUTH_DOMAIN: auth_domain if auth_domain else domain,
    }
    item[CONF_NAME] = credential.name if credential.name else DEFAULT_IMPORT_NAME
    await hass.data[DATA_COMPONENT].async_import_item(item)


class AuthImplementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """Application Credentials local oauth2 implementation."""

    def __init__(
        self,
        hass: HomeAssistant,
        auth_domain: str,
        credential: ClientCredential,
        authorization_server: AuthorizationServer,
    ) -> None:
        """Initialize AuthImplementation."""
        super().__init__(
            hass,
            auth_domain,
            credential.client_id,
            credential.client_secret,
            authorization_server.authorize_url,
            authorization_server.token_url,
        )
        self._name = credential.name

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return self._name or self.client_id


async def _async_provide_implementation(
    hass: HomeAssistant, domain: str
) -> list[config_entry_oauth2_flow.AbstractOAuth2Implementation]:
    """Return registered OAuth implementations."""

    platform = await _get_platform(hass, domain)
    if not platform:
        return []

    credentials = hass.data[DATA_COMPONENT].async_client_credentials(domain)
    if hasattr(platform, "async_get_auth_implementation"):
        return [
            await platform.async_get_auth_implementation(hass, auth_domain, credential)
            for auth_domain, credential in credentials.items()
        ]
    authorization_server = await platform.async_get_authorization_server(hass)
    return [
        AuthImplementation(hass, auth_domain, credential, authorization_server)
        for auth_domain, credential in credentials.items()
    ]


async def _async_config_entry_app_credentials(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> str | None:
    """Return the item id of an application credential for an existing ConfigEntry."""
    if not await _get_platform(hass, config_entry.domain) or not (
        auth_domain := config_entry.data.get("auth_implementation")
    ):
        return None

    for item in hass.data[DATA_COMPONENT].async_items():
        item_id = item[CONF_ID]
        if (
            item[CONF_DOMAIN] == config_entry.domain
            and item.get(CONF_AUTH_DOMAIN, item_id) == auth_domain
        ):
            return item_id
    return None


class ApplicationCredentialsProtocol(Protocol):
    """Define the format that application_credentials platforms may have.

    Most platforms typically just implement async_get_authorization_server, and
    the default oauth implementation will be used. Otherwise a platform may
    implement async_get_auth_implementation to give their use a custom
    AbstractOAuth2Implementation.
    """

    async def async_get_authorization_server(
        self, hass: HomeAssistant
    ) -> AuthorizationServer:
        """Return authorization server, for the default auth implementation."""

    async def async_get_auth_implementation(
        self, hass: HomeAssistant, auth_domain: str, credential: ClientCredential
    ) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
        """Return a custom auth implementation."""

    async def async_get_description_placeholders(
        self, hass: HomeAssistant
    ) -> dict[str, str]:
        """Return description placeholders for the credentials dialog."""


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
        platform = await integration.async_get_platform("application_credentials")
    except ImportError as err:
        _LOGGER.debug(
            "Integration '%s' does not provide application_credentials: %s",
            integration_domain,
            err,
        )
        return None
    if not hasattr(platform, "async_get_authorization_server") and not hasattr(
        platform, "async_get_auth_implementation"
    ):
        raise ValueError(
            f"Integration '{integration_domain}' platform {DOMAIN} did not implement"
            " 'async_get_authorization_server' or 'async_get_auth_implementation'"
        )
    return platform


async def _async_integration_config(hass: HomeAssistant, domain: str) -> dict[str, Any]:
    platform = await _get_platform(hass, domain)
    if platform and hasattr(platform, "async_get_description_placeholders"):
        placeholders = await platform.async_get_description_placeholders(hass)
        return {"description_placeholders": placeholders}
    return {}


@websocket_api.websocket_command(
    {vol.Required("type"): "application_credentials/config"}
)
@websocket_api.async_response
async def handle_integration_list(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle integrations command."""
    domains = await async_get_application_credentials(hass)
    result = {
        "domains": domains,
        "integrations": {
            domain: await _async_integration_config(hass, domain) for domain in domains
        },
    }
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "application_credentials/config_entry",
        vol.Required("config_entry_id"): str,
    }
)
@websocket_api.async_response
async def handle_config_entry(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return application credentials information for a config entry."""
    entry_id = msg["config_entry_id"]
    config_entry = hass.config_entries.async_get_entry(entry_id)
    if not config_entry:
        connection.send_error(
            msg["id"],
            "invalid_config_entry_id",
            f"Config entry not found: {entry_id}",
        )
        return
    result = {}
    if application_credentials_id := await _async_config_entry_app_credentials(
        hass, config_entry
    ):
        result["application_credentials_id"] = application_credentials_id
    connection.send_result(msg["id"], result)
