"""Test for Nord Pool component Init."""

from __future__ import annotations

from unittest.mock import patch

from pynordpool import (
    DeliveryPeriodData,
    NordPoolConnectionError,
    NordPoolEmptyResponseError,
    NordPoolError,
    NordPoolResponseError,
)
import pytest

from homeassistant.components.nordpool.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant, get_data: DeliveryPeriodData) -> None:
    """Test load and unload an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            return_value=get_data,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("error"),
    [
        (NordPoolConnectionError),
        (NordPoolEmptyResponseError),
        (NordPoolError),
        (NordPoolResponseError),
    ],
)
async def test_initial_startup_fails(
    hass: HomeAssistant, get_data: DeliveryPeriodData, error: Exception
) -> None:
    """Test load and unload an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            side_effect=error,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.SETUP_RETRY
