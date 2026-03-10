"""Tests for derivative diagnostics."""

from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, derivative_config_entry
) -> None:
    """Test diagnostics for config entry."""

    assert await hass.config_entries.async_setup(derivative_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, derivative_config_entry
    )

    assert isinstance(result, dict)
    assert result["config_entry"]["domain"] == "derivative"
    assert result["config_entry"]["options"]["name"] == "My derivative"
    assert result["entity"][0]["entity_id"] == "sensor.my_derivative"
