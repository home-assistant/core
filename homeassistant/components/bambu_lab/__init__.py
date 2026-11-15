"""The Bambu Lab integration."""

from aiobambulab import (
    BambuLabAuthenticationError,
    BambuLabCertificateError,
    BambuLabClient,
    BambuLabConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_ACCESS_CODE, CONF_SERIAL_NUMBER, DOMAIN

_PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SENSOR]

type BambuLabConfigEntry = ConfigEntry[BambuLabClient]


async def async_setup_entry(hass: HomeAssistant, entry: BambuLabConfigEntry) -> None:
    """Set up Bambu Lab from a config entry."""
    client = BambuLabClient(
        entry.data[CONF_HOST],
        entry.data[CONF_SERIAL_NUMBER],
        entry.data[CONF_ACCESS_CODE],
    )

    try:
        await client.connect()
    except BambuLabAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except BambuLabCertificateError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="wrong_device",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err
    except BambuLabConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err

    entry.runtime_data = client
    entry.async_on_unload(client.disconnect)

    async def _async_disconnect(event: Event) -> None:
        """Disconnect from the printer when Home Assistant stops."""
        await client.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect)
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: BambuLabConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
