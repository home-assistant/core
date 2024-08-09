"""The Mastodon integration."""

from __future__ import annotations

from dataclasses import dataclass

from mastodon.Mastodon import Mastodon, MastodonError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery

from .const import CONF_BASE_URL, DOMAIN
from .coordinator import MastodonCoordinator
from .utils import create_mastodon_client

PLATFORMS: list[Platform] = [Platform.NOTIFY, Platform.SENSOR]


@dataclass
class MastodonData:
    """Mastodon data type."""

    client: Mastodon
    instance: dict
    account: dict
    coordinator: MastodonCoordinator


type MastodonConfigEntry = ConfigEntry[MastodonData]


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

    coordinator = MastodonCoordinator(hass, client)

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


def setup_mastodon(entry: ConfigEntry) -> tuple[Mastodon, dict, dict]:
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
