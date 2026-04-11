"""Tests for the Kodi integration."""

from collections.abc import Sequence
from unittest.mock import patch

from homeassistant.components.kodi.const import CONF_WS_PORT, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .util import MockConnection, MockWSConnection

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant,
    *,
    call_method_return_value: dict[str, bool] | None = None,
    call_method_side_effect: Sequence[dict[str, bool]] | None = None,
    connection: MockConnection | MockWSConnection | None = None,
) -> MockConfigEntry:
    """Set up the Kodi integration in Home Assistant."""
    entry_data = {
        CONF_NAME: "name",
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 8080,
        CONF_WS_PORT: 9090,
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_SSL: False,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, title="name")
    entry.add_to_hass(hass)
    if call_method_return_value is None:
        call_method_return_value = {"System.ScreenSaverActive": False}
    if connection is None:
        connection = MockConnection()
    call_method_patch_kwargs: dict[str, object]
    if call_method_side_effect is None:
        call_method_patch_kwargs = {"return_value": call_method_return_value}
    else:
        call_method_patch_kwargs = {"side_effect": call_method_side_effect}

    with (
        patch("homeassistant.components.kodi.Kodi.ping", return_value=True),
        patch(
            "homeassistant.components.kodi.Kodi.call_method",
            **call_method_patch_kwargs,
        ),
        patch(
            "homeassistant.components.kodi.Kodi.get_players",
            return_value=[],
        ),
        patch(
            "homeassistant.components.kodi.Kodi.get_application_properties",
            return_value={"version": {"major": 1, "minor": 1}},
        ),
        patch(
            "homeassistant.components.kodi.get_kodi_connection",
            return_value=connection,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
