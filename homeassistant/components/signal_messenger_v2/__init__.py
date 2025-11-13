"""Signal Messenger v2 integration."""

from __future__ import annotations

from pysignalclirestapi import SignalCliRestApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery

from .const import DOMAIN
from .notify import get_api

type SignalConfigEntry = ConfigEntry[SignalCliRestApi]


async def async_setup_entry(hass: HomeAssistant, entry: SignalConfigEntry) -> bool:
    """Set up Signal Messenger v2 from a config entry."""

    api = get_api(entry.data.__dict__)

    try:
        api.about()
    except Exception as ex:
        raise ConfigEntryNotReady("Failed to connect to Signal CLI REST API") from ex

    entry.runtime_data = api

    await discovery.async_load_platform(
        hass, Platform.NOTIFY, DOMAIN, {**entry.data, "entry_id": entry.entry_id}, {}
    )

    return True
