"""Component for the Slide local API."""

from __future__ import annotations

import logging

from goslideapi.goslideapi import (
    ClientConnectionError,
    ClientTimeoutError,
    GoSlideLocal as SlideLocalApi,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_VERSION, CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

type SlideConfigEntry = ConfigEntry[SlideLocalApi]


PLATFORMS = [Platform.COVER]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: SlideConfigEntry) -> bool:
    """Set up the slide_local integration."""

    api_version = entry.data[CONF_API_VERSION]
    host = entry.data[CONF_HOST]
    password = entry.data[CONF_PASSWORD]

    api = SlideLocalApi()
    await api.slide_add(
        host,
        password,
        api_version,
    )

    try:
        slide_info = await api.slide_info(host)
    except (ClientConnectionError, ClientTimeoutError) as err:
        # https://developers.home-assistant.io/docs/integration_setup_failures/

        _LOGGER.debug(
            "Unable to get information from Slide '%s': %s",
            host,
            str(err),
        )

        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="config_entry_not_ready"
        ) from err

    if slide_info is None or slide_info.get("mac") is None:
        _LOGGER.error(
            "Unable to setup Slide Local '%s', the MAC is missing in the slide response (%s)"
        )
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="config_entry_not_ready"
        )

    entry.runtime_data = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SlideConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
