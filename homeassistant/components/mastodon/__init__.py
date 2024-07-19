"""The Mastodon integration."""

from __future__ import annotations

from mastodon.Mastodon import MastodonError, MastodonUnauthorizedError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NAME,
    CONF_PLATFORM,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery,
)
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BASE_URL,
    DATA_HASS_CONFIG,
    DEFAULT_NAME,
    DEFAULT_URL,
    DOMAIN,
    INSTANCE_VERSION,
)
from .coordinator import MastodonConfigEntry, MastodonCoordinator, MastodonData
from .utils import create_mastodon_instance

PLATFORMS: list[Platform] = [Platform.NOTIFY, Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Required(CONF_ACCESS_TOKEN): str,
                    vol.Optional(CONF_BASE_URL, default=DEFAULT_URL): cv.url,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Mastodon component."""
    if Platform.NOTIFY in config:
        for entry in config[Platform.NOTIFY]:
            if entry[CONF_PLATFORM] == DOMAIN:
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": SOURCE_IMPORT},
                        data={
                            CONF_CLIENT_ID: entry[CONF_CLIENT_ID],
                            CONF_CLIENT_SECRET: entry[CONF_CLIENT_SECRET],
                            CONF_ACCESS_TOKEN: entry[CONF_ACCESS_TOKEN],
                            CONF_NAME: entry.get(CONF_NAME, "Mastodon"),
                            CONF_BASE_URL: entry.get(CONF_BASE_URL, DEFAULT_URL),
                        },
                    )
                )

        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2025.1.0",
            is_fixable=False,
            is_persistent=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Mastodon",
            },
        )

    hass.data[DATA_HASS_CONFIG] = config

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mastodon from a config entry."""

    try:
        client = await hass.async_add_executor_job(
            create_mastodon_instance,
            entry.data[CONF_BASE_URL],
            entry.data[CONF_CLIENT_ID],
            entry.data[CONF_CLIENT_SECRET],
            entry.data[CONF_ACCESS_TOKEN],
        )
        instance: dict = await hass.async_add_executor_job(client.instance)

    except MastodonUnauthorizedError as ex:
        raise ConfigEntryAuthFailed from ex
    except MastodonError as ex:
        raise ConfigEntryNotReady("Failed to connect") from ex

    assert entry.unique_id
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        entry_type=DeviceEntryType.SERVICE,
        sw_version=instance.get(INSTANCE_VERSION),
    )

    coordinator = MastodonCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = MastodonData(client, coordinator)

    await discovery.async_load_platform(
        hass,
        Platform.NOTIFY,
        DOMAIN,
        {CONF_NAME: entry.title, "client": client},
        hass.data[DATA_HASS_CONFIG],
    )

    await hass.config_entries.async_forward_entry_setups(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MastodonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
