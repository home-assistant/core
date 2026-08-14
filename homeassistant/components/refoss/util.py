"""Refoss helpers functions."""

from collections.abc import Mapping
from typing import Any

from refoss_ha.discovery import Discovery

from homeassistant.const import CONF_HOST, CONF_HOSTS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import singleton


def configured_hosts(data: Mapping[str, Any]) -> list[str]:
    """Return the configured discovery targets."""
    if CONF_HOSTS in data:
        return list(data[CONF_HOSTS])
    if host := data.get(CONF_HOST):
        return [host]
    return []


@singleton.singleton("refoss_discovery_server")
async def refoss_discovery_server(hass: HomeAssistant) -> Discovery:
    """Get refoss Discovery server."""
    discovery_server = Discovery()
    await discovery_server.initialize()
    return discovery_server
