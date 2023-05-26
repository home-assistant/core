"""Tests for the Owlet integration."""
from __future__ import annotations

import json
from unittest.mock import patch

from homeassistant.components.owlet.const import (
    CONF_OWLET_EXPIRY,
    CONF_OWLET_REFRESH,
    DOMAIN,
    POLLING_INTERVAL,
)
from homeassistant.const import (
    CONF_API_TOKEN,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
    properties_fixture: str = "update_properties_charging.json",
    devices_fixture: str = "get_devices.json",
) -> MockConfigEntry:
    """Set up integration entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="sample@gmail.com",
        unique_id="sample@gmail.com",
        data={
            CONF_REGION: "europe",
            CONF_USERNAME: "sample@gmail.com",
            CONF_API_TOKEN: "api_token",
            CONF_OWLET_EXPIRY: 100,
            CONF_OWLET_REFRESH: "refresh_token",
        },
        options={CONF_SCAN_INTERVAL: POLLING_INTERVAL},
    )

    entry.add_to_hass(hass)

    if not skip_setup:
        with patch(
            "homeassistant.components.owlet.OwletAPI.get_properties",
            return_value=json.loads(load_fixture(properties_fixture, "owlet")),
        ), patch(
            "homeassistant.components.owlet.OwletAPI.authenticate", return_value=None
        ), patch(
            "homeassistant.components.owlet.OwletAPI.get_devices",
            return_value=json.loads(load_fixture(devices_fixture, "owlet")),
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

    return entry
