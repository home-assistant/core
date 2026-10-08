"""The OVHcloud AI Endpoints integration."""

from openai import (
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    OpenAIError,
    PermissionDeniedError,
)
from openai.types.chat import ChatCompletionUserMessageParam

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client

from .const import BASE_URL

PLATFORMS = [Platform.CONVERSATION]

type OVHcloudAIEndpointsConfigEntry = ConfigEntry[AsyncOpenAI]


def _create_client(hass: HomeAssistant, api_key: str) -> AsyncOpenAI:
    """Create the AsyncOpenAI client used by this integration."""
    return AsyncOpenAI(
        base_url=BASE_URL,
        api_key=api_key,
        http_client=get_async_client(hass),
    )


async def _validate_api_key(client: AsyncOpenAI) -> None:
    """Validate the API key against the chat completions endpoint.

    We send a chat completion request with an unknown ``extra_body`` field
    to prevent valid usage and billing.
    A valid key triggers a 400 (BadRequestError), which we treat as success.
    An invalid key triggers a 401 (AuthenticationError),which propagates
    along with any other exception.
    """
    try:
        await client.with_options(timeout=10.0).chat.completions.create(
            model="llama@latest",
            messages=[ChatCompletionUserMessageParam(role="user", content="ping")],
            extra_body={"foo": "bar"},
        )
    except BadRequestError:
        return


async def async_setup_entry(
    hass: HomeAssistant, entry: OVHcloudAIEndpointsConfigEntry
) -> bool:
    """Set up OVHcloud AI Endpoints from a config entry."""
    client = _create_client(hass, entry.data[CONF_API_KEY])

    try:
        await _validate_api_key(client)
    except (AuthenticationError, PermissionDeniedError) as err:
        raise ConfigEntryAuthFailed(err) from err
    except OpenAIError as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_entry(
    hass: HomeAssistant, entry: OVHcloudAIEndpointsConfigEntry
) -> None:
    """Reload the entry when its data or subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: OVHcloudAIEndpointsConfigEntry
) -> bool:
    """Unload OVHcloud AI Endpoints."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
