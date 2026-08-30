"""The Helty Flow Cloud integration."""

from pyheltycloud import HeltyCloud, HeltyCloudAuthError, HeltyCloudError

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import HeltyCloudConfigEntry, HeltyCloudDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.FAN]


async def async_setup_entry(hass: HomeAssistant, entry: HeltyCloudConfigEntry) -> bool:
    """Set up Helty Flow Cloud from a config entry."""
    client = HeltyCloud(
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )
    try:
        devices = await client.get_devices()
    except HeltyCloudAuthError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except HeltyCloudError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err

    coordinators = [
        HeltyCloudDataUpdateCoordinator(hass, entry, client, device)
        for device in devices
    ]
    # get_devices() has already proved the credentials and reached the cloud.
    # A unit with nothing to read past that point is a panel that has gone
    # quiet, which is a condition of that one device: let it come up
    # unavailable rather than hold back every other unit on the account.
    for coordinator in coordinators:
        await coordinator.async_refresh()

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeltyCloudConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
