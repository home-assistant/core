"""Test the Zeversolar coordinator."""

from unittest.mock import patch

from zeversolar.exceptions import ZeverSolarError

from homeassistant.core import HomeAssistant

from . import init_integration


async def test_coordinator_update_success(hass: HomeAssistant) -> None:
    """Test coordinator fetches data successfully."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data

    assert coordinator.last_update_success is True
    assert coordinator.data is not None


async def test_coordinator_update_failed(hass: HomeAssistant) -> None:
    """Test coordinator marks update failed when client raises ZeverSolarError."""
    entry = await init_integration(hass)
    coordinator = entry.runtime_data

    with patch(
        "zeversolar.ZeverSolarClient.get_data",
        side_effect=ZeverSolarError,
    ):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is False
