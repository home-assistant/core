"""KNX Telegrams Migration Tests."""

from __future__ import annotations

import json
import logging
import os
import uuid

from knx_telegram_store import TelegramQuery

from homeassistant.components.knx.const import (
    CONF_KNX_TELEGRAM_DB_BACKEND,
    CONF_KNX_TELEGRAM_DB_PATH,
    KNX_MODULE_KEY,
    TELEGRAM_BACKEND_SQLITE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR

from .conftest import KNXTestKit

_LOGGER = logging.getLogger("homeassistant.components.knx")
_LOGGER.setLevel(logging.DEBUG)


async def test_migrate_telegrams_json_to_sqlite(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test migrating telegrams from legacy JSON to SQLite."""
    legacy_path = hass.config.path(STORAGE_DIR, "knx/telegrams_history.json")
    os.makedirs(os.path.dirname(legacy_path), exist_ok=True)

    # 10 telegrams from user provided sample
    legacy_data = {
        "data": [
            {
                "destination": "3/2/100",
                "source": "1.0.6",
                "direction": "Incoming",
                "payload": [0],
                "telegramtype": "GroupValueWrite",
                "timestamp": "2026-05-07T23:34:45.127015+02:00",
                "value": 0,
                "source_name": "Source 1",
                "destination_name": "Dest 1",
                "data_secure": False,
                "dpt_main": 5,
                "dpt_sub": 1,
                "dpt_name": "percent",
                "unit": "%",
            },
            {
                "destination": "4/2/101",
                "source": "1.0.6",
                "direction": "Incoming",
                "payload": [255],
                "telegramtype": "GroupValueWrite",
                "timestamp": "2026-05-07T23:34:45.425139+02:00",
                "value": 100,
                "source_name": "Source 2",
                "destination_name": "Dest 2",
                "data_secure": False,
                "dpt_main": 5,
                "dpt_sub": 1,
                "dpt_name": "percent",
                "unit": "%",
            },
            {
                "destination": "1/2/11",
                "source": "1.0.32",
                "direction": "Incoming",
                "payload": [7, 158],
                "telegramtype": "GroupValueWrite",
                "timestamp": "2026-05-07T23:34:53.690501+02:00",
                "value": 19.5,
                "source_name": "Source 3",
                "destination_name": "Dest 3",
                "data_secure": False,
                "dpt_main": 9,
                "dpt_sub": 1,
                "dpt_name": "temperature",
                "unit": "°C",
            },
            {
                "destination": "3/7/62",
                "source": "1.0.255",
                "direction": "Incoming",
                "payload": None,
                "telegramtype": "GroupValueRead",
                "timestamp": "2026-05-07T23:35:05.898527+02:00",
                "value": None,
                "source_name": "Source 4",
                "destination_name": "Dest 4",
                "data_secure": False,
                "dpt_main": None,
                "dpt_sub": None,
                "dpt_name": None,
                "unit": None,
            },
            {
                "destination": "1/4/100",
                "source": "1.0.45",
                "direction": "Incoming",
                "payload": 1,
                "telegramtype": "GroupValueWrite",
                "timestamp": "2026-05-07T23:35:12.778950+02:00",
                "value": "on",
                "source_name": "Source 5",
                "destination_name": "Dest 5",
                "data_secure": False,
                "dpt_main": 1,
                "dpt_sub": 1,
                "dpt_name": "switch",
                "unit": None,
            },
            {
                "destination": "2/4/61",
                "source": "1.0.18",
                "direction": "Incoming",
                "payload": [0, 100],
                "telegramtype": "GroupValueWrite",
                "timestamp": "2026-05-07T23:35:28.373347+02:00",
                "value": 1.0,
                "source_name": "Source 6",
                "destination_name": "Dest 6",
                "data_secure": False,
                "dpt_main": 9,
                "dpt_sub": 4,
                "dpt_name": "illuminance",
                "unit": "lx",
            },
            {
                "destination": "0/6/0",
                "source": "1.0.1",
                "direction": "Incoming",
                "payload": [77, 53, 32, 83, 48, 32, 65, 51, 51, 53, 32, 69, 48, 48],
                "telegramtype": "GroupValueWrite",
                "timestamp": "2026-05-07T23:35:58.858017+02:00",
                "value": "M5 S0 A335 E00",
                "source_name": "Source 7",
                "destination_name": "Dest 7",
                "data_secure": False,
                "dpt_main": 16,
                "dpt_sub": 0,
                "dpt_name": "string",
                "unit": None,
            },
            {
                "destination": "0/1/100",
                "source": "1.0.255",
                "direction": "Incoming",
                "payload": [4, 176],
                "telegramtype": "GroupValueWrite",
                "timestamp": "2026-05-07T23:36:05.509221+02:00",
                "value": 12.0,
                "source_name": "Source 8",
                "destination_name": "Dest 8",
                "data_secure": False,
                "dpt_main": 9,
                "dpt_sub": 1,
                "dpt_name": "temperature",
                "unit": "°C",
            },
            {
                "destination": "4/2/11",
                "source": "1.0.31",
                "direction": "Incoming",
                "payload": [12, 131],
                "telegramtype": "GroupValueWrite",
                "timestamp": "2026-05-07T23:36:32.343434+02:00",
                "value": 23.1,
                "source_name": "Source 9",
                "destination_name": "Dest 9",
                "data_secure": False,
                "dpt_main": 9,
                "dpt_sub": 1,
                "dpt_name": "temperature",
                "unit": "°C",
            },
            {
                "destination": "1/2/51",
                "source": "1.0.21",
                "direction": "Incoming",
                "payload": [12, 79],
                "telegramtype": "GroupValueResponse",
                "timestamp": "2026-05-07T23:36:58.932929+02:00",
                "value": 22.06,
                "source_name": "Source 10",
                "destination_name": "Dest 10",
                "data_secure": False,
                "dpt_main": 9,
                "dpt_sub": 1,
                "dpt_name": "temperature",
                "unit": "°C",
            },
        ]
    }

    def _write_legacy_data() -> None:
        with open(legacy_path, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

    await hass.async_add_executor_job(_write_legacy_data)

    # Setup integration with SQLite (unique filename)
    db_name = f"test_telegrams_{uuid.uuid4().hex}.db"
    knx.mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        knx.mock_config_entry,
        data=knx.mock_config_entry.data
        | {
            CONF_KNX_TELEGRAM_DB_BACKEND: TELEGRAM_BACKEND_SQLITE,
            CONF_KNX_TELEGRAM_DB_PATH: db_name,
        },
    )

    await knx.setup_integration(add_entry_to_hass=False)
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams

    await hass.async_block_till_done()

    # Verify migration
    result = await telegrams_module.store.query(TelegramQuery(order_descending=False))
    assert len(result.telegrams) == 10

    # Check normalization: [0] -> (0,)
    # Note: Backend might return list even if stored as tuple due to JSON serialization
    assert result.telegrams[0].destination == "3/2/100"
    assert tuple(result.telegrams[0].payload) == (0,)

    # Check normalization: [7, 158] -> (7, 158)
    assert result.telegrams[2].destination == "1/2/11"
    assert tuple(result.telegrams[2].payload) == (7, 158)

    # Check None payload stays None
    assert result.telegrams[3].destination == "3/7/62"
    assert result.telegrams[3].payload is None

    # Check int payload stays int
    assert result.telegrams[4].destination == "1/4/100"
    assert result.telegrams[4].payload == 1

    # Check long string payload
    assert result.telegrams[6].destination == "0/6/0"
    assert tuple(result.telegrams[6].payload) == (
        77,
        53,
        32,
        83,
        48,
        32,
        65,
        51,
        51,
        53,
        32,
        69,
        48,
        48,
    )

    # Verify legacy file removal
    assert not os.path.exists(legacy_path)

    # Cleanup DB file
    db_path = hass.config.path(db_name)
    if os.path.exists(db_path):
        os.remove(db_path)
