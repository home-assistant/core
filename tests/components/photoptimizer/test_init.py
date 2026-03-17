"""Test the photoptimizer integration setup behavior."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.photoptimizer import async_setup_entry
from homeassistant.components.photoptimizer.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def _raise_emhass_update_failed() -> None:
    """Raise ConfigEntryNotReady caused by an EMHASS update failure."""
    raise ConfigEntryNotReady from UpdateFailed("EMHASS optimization failed")


async def _raise_non_emhass_update_failed() -> None:
    """Raise ConfigEntryNotReady caused by a different update failure."""
    raise ConfigEntryNotReady from UpdateFailed("Forecast.Solar API error")


async def test_setup_entry_loads_when_emhass_first_refresh_fails(
    hass: HomeAssistant,
) -> None:
    """Test setup continues when first refresh fails due to EMHASS unavailability."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"latitude": 49.5962536, "longitude": 18.3395664},
    )
    config_entry.add_to_hass(hass)

    forecast_client = AsyncMock()
    forecast_client.estimate.return_value = object()

    with (
        patch(
            "homeassistant.components.photoptimizer.ForecastSolar",
            return_value=forecast_client,
        ),
        patch(
            "homeassistant.components.photoptimizer.PhotoptimizerCoordinator.async_config_entry_first_refresh",
            side_effect=_raise_emhass_update_failed,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        assert await async_setup_entry(hass, config_entry)

    assert config_entry.entry_id in hass.data[DOMAIN]
    assert config_entry.runtime_data is hass.data[DOMAIN][config_entry.entry_id]


async def test_setup_entry_raises_for_non_emhass_first_refresh_failure(
    hass: HomeAssistant,
) -> None:
    """Test setup still retries when the first refresh fails for other reasons."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"latitude": 49.5962536, "longitude": 18.3395664},
    )
    config_entry.add_to_hass(hass)

    forecast_client = AsyncMock()
    forecast_client.estimate.return_value = object()

    with (
        patch(
            "homeassistant.components.photoptimizer.ForecastSolar",
            return_value=forecast_client,
        ),
        patch(
            "homeassistant.components.photoptimizer.PhotoptimizerCoordinator.async_config_entry_first_refresh",
            side_effect=_raise_non_emhass_update_failed,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, config_entry)
