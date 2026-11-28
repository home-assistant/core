"""Home Assistant glue for the Sign in with ChatGPT (ChatGPT plan) flow.

The protocol lives in the ``chatgpt-plan-auth`` library, which carries no Home
Assistant imports, no ``hass`` and no storage. What is left here is Home
Assistant specific: config entry inspection, the storage backed host id, the
shared Home Assistant HTTP client, the config entry aware token lifecycle and
the mapping of the library's errors onto Home Assistant's.
"""

from collections.abc import Mapping
from typing import Any, override

from chatgpt_plan_auth import (
    CLIENT_ID_PREFIX,
    PLAN_SCOPE,
    RESOURCE,
    AuthorizationRequest,
    ChatGPTAuth as LibraryChatGPTAuth,
    ChatGPTCredentials,
    ChatGPTPlanAuthError,
    ChatGPTPlanAuthFatalError,
    async_get_subscription_models as library_get_subscription_models,
    async_get_subscription_models_for_credentials as library_get_subscription_models_for_credentials,
    async_token_request as library_token_request,
    create_authorization_request as library_create_authorization_request,
    create_ext_agent_host_id,
    credentials_from_token,
    parse_callback_url,
    shape_request_for_subscription,
    subscription_error_message,
    subscription_model_options,
    validate_id_token,
)
from chatgpt_plan_auth.client import ChatGPTSubscriptionClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.storage import Store

from .const import AUTH_METHOD_CHATGPT, CONF_AUTH_METHOD, CONF_EXT_AGENT_HOST_ID

# Name of this application in the ChatGPT account's registered clients.
AGENT_NAME_HINT = "Home Assistant"

# The host id identifies the host the app runs on, not the signed in account,
# and every registration of this instance shares it. It is kept in Home
# Assistant storage instead of the config entry so that it survives entry
# deletion and re-registration.
STORAGE_KEY = "openai_conversation.chatgpt"
STORAGE_VERSION = 1


def is_chatgpt_entry(entry: ConfigEntry) -> bool:
    """Return if a config entry authenticates with a ChatGPT plan.

    API key entries keep the historical layout and have no auth method key.
    """
    return entry.data.get(CONF_AUTH_METHOD) == AUTH_METHOD_CHATGPT


async def async_get_agent_host_id(hass: HomeAssistant) -> str:
    """Return the stable ``ext_agent_host_id`` of this installation.

    A UUID based host id is documented as a supported alternative to a JWK
    thumbprint URI and needs no key management.
    """
    store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    if (stored := await store.async_load()) and (
        host_id := stored.get(CONF_EXT_AGENT_HOST_ID)
    ):
        if isinstance(host_id, str):
            return host_id
    host_id = create_ext_agent_host_id()
    await store.async_save({CONF_EXT_AGENT_HOST_ID: host_id})
    return host_id


def create_authorization_request(
    *,
    client_id: str | None,
    ext_agent_host_id: str,
    id_token_hint: str | None = None,
) -> AuthorizationRequest:
    """Build the authorization URL for a new or a returning ChatGPT account."""
    return library_create_authorization_request(
        client_id=client_id,
        ext_agent_host_id=ext_agent_host_id,
        id_token_hint=id_token_hint,
        agent_name_hint=AGENT_NAME_HINT,
    )


async def async_token_request(
    hass: HomeAssistant,
    data: dict[str, str],
    *,
    fatal_errors: bool = False,
) -> dict[str, Any]:
    """POST a form encoded grant to the SIWC token endpoint.

    ``fatal_errors`` maps the errors which invalidate the stored refresh token
    to `ConfigEntryAuthFailed` so Home Assistant starts the reauth flow.
    """
    try:
        return await library_token_request(
            get_async_client(hass), data, fatal_errors=fatal_errors
        )
    except ChatGPTPlanAuthFatalError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except ChatGPTPlanAuthError as err:
        raise HomeAssistantError(str(err)) from err


async def async_validate_id_token(
    hass: HomeAssistant, id_token: str, *, client_id: str, nonce: str
) -> Mapping[str, Any]:
    """Validate an ID token of one authorization attempt and return its claims."""
    try:
        return validate_id_token(id_token, client_id=client_id, nonce=nonce)
    except ChatGPTPlanAuthError as err:
        raise HomeAssistantError(str(err)) from err


async def async_get_subscription_models(
    hass: HomeAssistant, auth: LibraryChatGPTAuth
) -> list[str]:
    """Return the model slugs offered to a ChatGPT plan account."""
    try:
        return await library_get_subscription_models(get_async_client(hass), auth)
    except ChatGPTPlanAuthFatalError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except ChatGPTPlanAuthError as err:
        raise HomeAssistantError(str(err)) from err


async def async_get_subscription_models_for_credentials(
    hass: HomeAssistant, credentials: ChatGPTCredentials
) -> list[str]:
    """Return the model slugs of an account which is not stored in an entry."""
    try:
        return await library_get_subscription_models_for_credentials(
            get_async_client(hass), credentials
        )
    except ChatGPTPlanAuthFatalError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except ChatGPTPlanAuthError as err:
        raise HomeAssistantError(str(err)) from err


class ChatGPTAuth(LibraryChatGPTAuth):
    """Manage the SIWC token lifecycle of one config entry.

    The library manager refreshes through the given client and reports every
    rotation; this binds both to Home Assistant: the shared client, persisting
    the rotated credentials on the entry and starting the reauth flow when the
    refresh token is dead.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        credentials: ChatGPTCredentials,
    ) -> None:
        """Initialize the token manager."""
        super().__init__(
            credentials, client=get_async_client(hass), on_update=self._async_store
        )
        self.hass = hass
        self.entry = entry
        self._reauth_started = False

    @classmethod
    def from_entry(cls, hass: HomeAssistant, entry: ConfigEntry) -> ChatGPTAuth:
        """Build the token manager of a config entry."""
        return cls(hass, entry, ChatGPTCredentials.from_entry_data(entry.data))

    @override
    async def async_get_access_token(self) -> str:
        """Return a valid access token, refreshing it when it is about to expire."""
        try:
            return await super().async_get_access_token()
        except ChatGPTPlanAuthFatalError as err:
            self._async_start_reauth()
            raise ConfigEntryAuthFailed(str(err)) from err

    @override
    async def async_handle_authentication_error(self) -> None:
        """Refresh the token after the API rejected the access token."""
        try:
            await super().async_handle_authentication_error()
        except ChatGPTPlanAuthFatalError as err:
            self._async_start_reauth()
            raise ConfigEntryAuthFailed(str(err)) from err

    @callback
    def _async_store(self, credentials: ChatGPTCredentials) -> None:
        """Persist the (rotated) credentials atomically."""
        self.hass.config_entries.async_update_entry(
            self.entry, data=credentials.as_entry_data()
        )

    @callback
    def _async_start_reauth(self) -> None:
        """Start the reauth flow, once."""
        if self._reauth_started:
            return
        self._reauth_started = True
        self.entry.async_start_reauth(self.hass)


__all__ = [
    "CLIENT_ID_PREFIX",
    "PLAN_SCOPE",
    "RESOURCE",
    "AuthorizationRequest",
    "ChatGPTAuth",
    "ChatGPTCredentials",
    "ChatGPTPlanAuthError",
    "ChatGPTPlanAuthFatalError",
    "ChatGPTSubscriptionClient",
    "async_get_agent_host_id",
    "async_get_subscription_models",
    "async_get_subscription_models_for_credentials",
    "async_token_request",
    "async_validate_id_token",
    "create_authorization_request",
    "credentials_from_token",
    "is_chatgpt_entry",
    "parse_callback_url",
    "shape_request_for_subscription",
    "subscription_error_message",
    "subscription_model_options",
]
