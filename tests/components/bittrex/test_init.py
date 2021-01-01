"""Test init of Bittrex integration."""
from homeassistant.components.bittrex.const import DOMAIN
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_registry


async def test_setup(hass):
    """Test that we can retrieve market info."""
    entry = MockConfigEntry(domain=DOMAIN, title="ZRX-USD, ZRX-USDT")
    entry.add_to_hass(hass)

    mock_registry(
        hass,
        {
            "sensor.bittrex_ticker_zrx_usd": entity_registry.RegistryEntry(
                entity_id="sensor.bittrex_ticker_zrx_usd",
                unique_id="1234",
                platform="bittrex",
                config_entry_id=entry.entry_id,
            ),
            "sensor.bittrex_ticker_zrx_usdt": entity_registry.RegistryEntry(
                entity_id="sensor.bittrex_ticker_zrx_usdt",
                unique_id="56789",
                platform="bittrex",
                config_entry_id=entry.entry_id,
            ),
        },
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    ent_reg = await entity_registry.async_get_registry(hass)

    ent_reg.async_get("sensor.bittrex_ticker_zrx_usd")
    ent_reg.async_get("sensor.bittrex_ticker_zrx_usdt")
