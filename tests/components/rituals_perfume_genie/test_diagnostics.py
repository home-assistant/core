"""Tests for the diagnostics data provided by the Rituals Perfume Genie integration."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .common import init_integration, mock_config_entry, mock_diffuser

from tests.common import async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    config_entry = mock_config_entry(unique_id="number_test")
    diffuser = mock_diffuser(hublot="lot123", perfume_amount=2)
    await init_integration(hass, config_entry, [diffuser])

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )


async def test_diagnostics_diffuser_added(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test diagnostics with a diffuser added to the account after setup."""
    config_entry = mock_config_entry(unique_id="diagnostics_diffuser_added")
    diffusers = [mock_diffuser(hublot="lot123")]
    await init_integration(hass, config_entry, diffusers)

    diffusers.append(mock_diffuser(hublot="lot456"))
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert len(diagnostics["diffusers"]) == 2
    assert diagnostics["diffusers"][0]["sensors"] is not None
    assert diagnostics["diffusers"][1]["sensors"] is None
