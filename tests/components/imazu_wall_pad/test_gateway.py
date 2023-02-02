"""Test the Imazu Wall Pad gateway."""


from homeassistant.core import HomeAssistant

from . import async_setup
from .const import UNSUPPORTED_DEVICE_PACKET


async def test_not_supported_packet(hass: HomeAssistant, mock_imazu_client):
    """Test for not supported packet the gateway."""
    entry = await async_setup(hass)

    test_packet = bytes.fromhex(UNSUPPORTED_DEVICE_PACKET)
    await mock_imazu_client.async_receive_packet(test_packet)
    await hass.async_block_till_done()

    entity_registry = hass.helpers.entity_registry.async_get(hass)
    entities = hass.helpers.entity_registry.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    )
    assert len(entities) == 0
