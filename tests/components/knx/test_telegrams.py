"""KNX Telegrams Tests."""

from __future__ import annotations

from knx_telegram_store import TelegramQuery

from homeassistant.components.knx.const import (
    CONF_KNX_TELEGRAM_DB_BACKEND,
    CONF_KNX_TELEGRAM_DB_PATH,
    KNX_MODULE_KEY,
    TELEGRAM_BACKEND_SQLITE,
)
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit


async def test_store_telegram_history(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test storing telegram history."""
    knx.mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        knx.mock_config_entry,
        data=knx.mock_config_entry.data
        | {
            CONF_KNX_TELEGRAM_DB_PATH: ":memory:",
        },
    )
    await knx.setup_integration(add_entry_to_hass=False)
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams

    await knx.receive_write("1/3/4", True)
    await hass.services.async_call(
        "knx", "send", {"address": "2/2/2", "payload": [1, 2, 3, 4]}, blocking=True
    )
    await knx.assert_write("2/2/2", (1, 2, 3, 4))

    # Wait for async store task
    await hass.async_block_till_done()

    # Verify in Memory store
    result = await telegrams_module.store.query(TelegramQuery(order_descending=False))
    assert len(result.telegrams) == 2
    assert result.telegrams[0].destination == "1/3/4"
    assert result.telegrams[1].destination == "2/2/2"


async def test_store_telegram_history_sqlite(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test storing telegram history in SQLite."""
    knx.mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        knx.mock_config_entry,
        data=knx.mock_config_entry.data
        | {
            CONF_KNX_TELEGRAM_DB_BACKEND: TELEGRAM_BACKEND_SQLITE,
            CONF_KNX_TELEGRAM_DB_PATH: ":memory:",
        },
    )
    await knx.setup_integration(add_entry_to_hass=False)
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams

    await knx.receive_write("1/3/4", True)
    await hass.async_block_till_done()

    # Verify in SQLite store
    result = await telegrams_module.store.query(TelegramQuery())
    assert len(result.telegrams) == 1
    assert result.telegrams[0].destination == "1/3/4"
