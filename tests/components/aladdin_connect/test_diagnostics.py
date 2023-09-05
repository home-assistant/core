"""Test AccuWeather diagnostics."""
from syrupy import SnapshotAssertion

from homeassistant.components.aladdin_connect.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

YAML_CONFIG = {"username": "test-user", "password": "test-password"}


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=YAML_CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot
