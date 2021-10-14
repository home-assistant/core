"""Tests for the BlueCurrent integration."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.bluecurrent import DOMAIN

from tests.common import MockConfigEntry


async def init_integration(
    hass, platform, data: dict, charge_point: dict, grid=None
) -> MockConfigEntry:
    """Set up the bluecurrent integration in Home Assistant."""

    if charge_point:
        data["101"].update(charge_point)

    if grid is None:
        grid = {}

    with patch("homeassistant.components.bluecurrent.PLATFORMS", [platform]), patch(
        "homeassistant.components.bluecurrent.Client", autospec=True
    ), patch("homeassistant.components.bluecurrent.Connector.grid", grid), patch(
        "homeassistant.components.bluecurrent.Connector.charge_points", data
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="uuid",
            unique_id="uuid",
            data={"api_token": "123", "card": {"123"}},
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry
