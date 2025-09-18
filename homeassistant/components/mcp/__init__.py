"""The Model Context Protocol integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, llm

from .application_credentials import authorization_server_context
from .const import CONF_ACCESS_TOKEN, CONF_AUTHORIZATION_URL, CONF_TOKEN_URL, DOMAIN
from .coordinator import ModelContextProtocolCoordinator, TokenManager
from .types import ModelContextProtocolConfigEntry

__all__ = [
    "DOMAIN",
    "async_setup_entry",
    "async_unload_entry",
]

API_PROMPT = "The following tools are available from a remote server named {name}."


async def async_get_config_entry_implementation(
    hass: HomeAssistant, entry: ModelContextProtocolConfigEntry
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation | None:
    """OAuth implementation for the config entry."""
    if "auth_implementation" not in entry.data:
        return None
    with authorization_server_context(
        AuthorizationServer(
            authorize_url=entry.data[CONF_AUTHORIZATION_URL],
            token_url=entry.data[CONF_TOKEN_URL],
        )
    ):
        return await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )


async def _create_token_manager(
    hass: HomeAssistant, entry: ModelContextProtocolConfigEntry
) -> TokenManager | None:
    """Create a OAuth token manager for the config entry if the server requires authentication."""
    if not (implementation := await async_get_config_entry_implementation(hass, entry)):
        return None

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    async def token_manager() -> str:
        await session.async_ensure_token_valid()
        return cast(str, session.token[CONF_ACCESS_TOKEN])

    return token_manager


async def async_setup_entry(
    hass: HomeAssistant, entry: ModelContextProtocolConfigEntry
) -> bool:
    """Set up Model Context Protocol from a config entry."""
    token_manager = await _create_token_manager(hass, entry)
    coordinator = ModelContextProtocolCoordinator(hass, entry, token_manager)
    await coordinator.async_config_entry_first_refresh()

    unsub = llm.async_register_api(
        hass,
        ModelContextProtocolAPI(
            hass=hass,
            id=f"{DOMAIN}-{entry.entry_id}",
            name=entry.title,
            coordinator=coordinator,
        ),
    )
    entry.async_on_unload(unsub)

    entry.runtime_data = coordinator

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ModelContextProtocolConfigEntry
) -> bool:
    """Unload a config entry."""
    return True


@dataclass(kw_only=True)
class ModelContextProtocolAPI(llm.API):
    """Define an object to hold the Model Context Protocol API."""

    coordinator: ModelContextProtocolCoordinator

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the instance of the API."""
        return llm.APIInstance(
            self,
            API_PROMPT.format(name=self.name),
            llm_context,
            tools=self.coordinator.data,
        )
