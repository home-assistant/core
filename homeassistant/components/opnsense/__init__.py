"""Support for OPNsense Routers."""

from aiopnsense import (
    OPNsenseBelowMinFirmware,
    OPNsenseClient,
    OPNsenseConnectionError,
    OPNsenseInvalidAuth,
    OPNsenseInvalidURL,
    OPNsensePrivilegeMissing,
    OPNsenseSSLError,
    OPNsenseTimeoutError,
    OPNsenseUnknownFirmware,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_API_SECRET, CONF_TRACKER_INTERFACES, DOMAIN
from .types import OPNsenseConfigEntry, OPNsenseRuntimeData

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_API_SECRET): cv.string,
                vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
                vol.Optional(CONF_TRACKER_INTERFACES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OPNsense component."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(_async_setup(hass, config))

    return True


async def _async_setup(hass: HomeAssistant, config: ConfigType) -> None:
    """Set up the OPNsense component from YAML."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config[DOMAIN],
    )


async def async_setup_entry(
    hass: HomeAssistant, config_entry: OPNsenseConfigEntry
) -> bool:
    """Set up the OPNsense component from a config entry."""
    url = config_entry.data[CONF_URL]
    session = async_get_clientsession(
        hass, verify_ssl=config_entry.data[CONF_VERIFY_SSL]
    )
    client = OPNsenseClient(
        url,
        config_entry.data[CONF_API_KEY],
        config_entry.data[CONF_API_SECRET],
        session,
        opts={"verify_ssl": config_entry.data[CONF_VERIFY_SSL]},
    )
    tracker_interfaces = config_entry.data.get(CONF_TRACKER_INTERFACES, [])
    try:
        await client.validate()
        if tracker_interfaces:
            interfaces_resp = await client.get_interfaces()
    except OPNsenseUnknownFirmware as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unknown_firmware",
            translation_placeholders={"url": url},
        ) from err
    except OPNsenseBelowMinFirmware as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="firmware_too_old",
            translation_placeholders={"url": url},
        ) from err
    except OPNsenseInvalidURL as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_url",
            translation_placeholders={"url": url},
        ) from err
    except OPNsenseTimeoutError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="timeout_connecting",
            translation_placeholders={"url": url},
        ) from err
    except OPNsenseSSLError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="ssl_error",
            translation_placeholders={"url": url},
        ) from err
    except OPNsenseInvalidAuth as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders={"url": url},
        ) from err
    except OPNsensePrivilegeMissing as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="privilege_missing",
            translation_placeholders={"url": url},
        ) from err
    except OPNsenseConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"url": url},
        ) from err

    if tracker_interfaces:
        # Verify that specified tracker interfaces are valid
        known_interfaces = [
            name for ifinfo in interfaces_resp.values() if (name := ifinfo.get("name"))
        ]
        for intf_description in tracker_interfaces:
            if intf_description not in known_interfaces:
                raise ConfigEntryError(
                    translation_domain=DOMAIN,
                    translation_key="tracker_interface_not_found",
                    translation_placeholders={
                        "interface": intf_description,
                        "known": ", ".join(known_interfaces),
                    },
                )

    config_entry.runtime_data = OPNsenseRuntimeData(
        client=client,
        tracker_interfaces=tracker_interfaces,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: OPNsenseConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
