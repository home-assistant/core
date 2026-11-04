"""The Amazon Polly integration."""

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_ACCESS_KEY_ID, CONF_REGION, CONF_SECRET_ACCESS_KEY, DOMAIN
from .helpers import AmazonPollyConfigEntry, CannotConnect, InvalidAuth, async_connect

PLATFORMS: list[Platform] = [Platform.TTS]


async def async_setup_entry(hass: HomeAssistant, entry: AmazonPollyConfigEntry) -> None:
    """Set up Amazon Polly from a config entry."""
    try:
        entry.runtime_data = await async_connect(
            hass,
            region=entry.data[CONF_REGION],
            access_key_id=entry.data[CONF_ACCESS_KEY_ID],
            secret_access_key=entry.data[CONF_SECRET_ACCESS_KEY],
        )
    except InvalidAuth as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except CannotConnect as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    async def _async_close_client(_: Event) -> None:
        await entry.runtime_data.client.__aexit__(None, None, None)

    # Config entries aren't unloaded on shutdown, so close the client then too.
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_client)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: AmazonPollyConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    await entry.runtime_data.client.__aexit__(None, None, None)
