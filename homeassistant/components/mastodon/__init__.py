"""The Mastodon integration."""

from __future__ import annotations

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
from .utils import create_mastodon_client


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mastodon from a config entry."""

    try:
        client, _, _ = await hass.async_add_executor_job(
            setup_mastodon,
            entry,
        )

    except MastodonError as ex:
        raise ConfigEntryNotReady("Failed to connect") from ex

    assert entry.unique_id

    await discovery.async_load_platform(
        hass,
        Platform.NOTIFY,
        DOMAIN,
        {CONF_NAME: entry.title, "client": client},
        {},
    )

    return True


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
