"""The Mastodon integration."""

from __future__ import annotations

from mastodon.Mastodon import Account, Instance, InstanceV2, Mastodon, MastodonError

from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .const import CONF_BASE_URL, DOMAIN, LOGGER
from .coordinator import MastodonConfigEntry, MastodonCoordinator, MastodonData
from .services import setup_services
from .utils import construct_mastodon_username, create_mastodon_client

PLATFORMS: list[Platform] = [Platform.NOTIFY, Platform.SENSOR]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Mastodon component."""
    setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MastodonConfigEntry) -> bool:
    """Set up Mastodon from a config entry."""

    try:
        client, instance, account = await hass.async_add_executor_job(
            setup_mastodon,
            entry,
        )

    except MastodonError as ex:
        raise ConfigEntryNotReady("Failed to connect") from ex

    assert entry.unique_id

    coordinator = MastodonCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = MastodonData(client, instance, account, coordinator)

    await discovery.async_load_platform(
        hass,
        Platform.NOTIFY,
        DOMAIN,
        {CONF_NAME: entry.title, "client": client},
        {},
    )

    await hass.config_entries.async_forward_entry_setups(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MastodonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )


async def async_migrate_entry(hass: HomeAssistant, entry: MastodonConfigEntry) -> bool:
    """Migrate old config."""

    if entry.version == 1 and entry.minor_version == 1:
        # Version 1.1 had the unique_id as client_id, this isn't necessarily unique
        LOGGER.debug("Migrating config entry from version %s", entry.version)

        try:
            _, instance, account = await hass.async_add_executor_job(
                setup_mastodon,
                entry,
            )
        except MastodonError as ex:
            LOGGER.error("Migration failed with error %s", ex)
            return False

        hass.config_entries.async_update_entry(
            entry,
            minor_version=2,
            unique_id=slugify(construct_mastodon_username(instance, account)),
        )

        LOGGER.debug(
            "Entry %s successfully migrated to version %s.%s",
            entry.entry_id,
            entry.version,
            entry.minor_version,
        )

    return True


def setup_mastodon(
    entry: MastodonConfigEntry,
) -> tuple[Mastodon, InstanceV2 | Instance, Account]:
    """Get mastodon details."""
    client = create_mastodon_client(
        entry.data[CONF_BASE_URL],
        entry.data[CONF_CLIENT_ID],
        entry.data[CONF_CLIENT_SECRET],
        entry.data[CONF_ACCESS_TOKEN],
    )

    instance = client.instance()
    account = client.account_verify_credentials()

    return client, instance, account
