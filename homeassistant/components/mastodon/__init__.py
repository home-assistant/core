"""The Mastodon integration."""

from __future__ import annotations

from mastodon.Mastodon import MastodonError

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
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery,
)
from homeassistant.helpers.device_registry import DeviceEntryType

from .const import CONF_BASE_URL, DOMAIN, INSTANCE_VERSION
from .utils import create_mastodon_instance

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


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
        await hass.async_add_executor_job(client.account_verify_credentials)

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

    await discovery.async_load_platform(
        hass,
        Platform.NOTIFY,
        DOMAIN,
        {CONF_NAME: entry.title, "client": client},
        {},
    )

    return True
