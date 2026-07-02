"""KNX Telegrams Migration Tests."""

from __future__ import annotations

import os
from typing import Any

from knx_telegram_store import TelegramQuery
import pytest

from homeassistant.components.knx.const import DOMAIN, KNX_MODULE_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .conftest import KNXTestKit

from tests.common import async_load_json_object_fixture


async def test_migrate_telegrams_json_to_sqlite(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test migrating telegrams from legacy JSON to SQLite."""
    store = Store[dict[str, Any]](hass, version=1, key="knx/telegrams_history.json")
    legacy_path = store.path

    legacy_data = await async_load_json_object_fixture(
        hass, "telegrams_history.json", DOMAIN
    )

    # The legacy KNX store saved the telegram list directly, so async_load()
    # returns the list. Save the inner list, not the fixture wrapper dict.
    await store.async_save(legacy_data["data"])

    await knx.setup_integration()
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams

    await hass.async_block_till_done()

    # Verify migration
    assert telegrams_module.store is not None
    result = await telegrams_module.store.query(TelegramQuery(order_descending=False))
    assert len(result.telegrams) == 10

    # Check normalization: [0] -> (0,)
    # Note: Backend might return list even if stored as tuple due to JSON serialization
    assert result.telegrams[0].destination == "3/2/100"
    payload_0 = result.telegrams[0].payload
    assert isinstance(payload_0, (list, tuple))
    assert tuple(payload_0) == (0,)

    # Check normalization: [7, 158] -> (7, 158)
    assert result.telegrams[2].destination == "1/2/11"
    payload_2 = result.telegrams[2].payload
    assert isinstance(payload_2, (list, tuple))
    assert tuple(payload_2) == (7, 158)

    # Check None payload stays None
    assert result.telegrams[3].destination == "3/7/62"
    assert result.telegrams[3].payload is None

    # Check int payload stays int
    assert result.telegrams[4].destination == "1/4/100"
    assert result.telegrams[4].payload == 1

    # Check long string payload
    assert result.telegrams[6].destination == "0/6/0"
    payload_6 = result.telegrams[6].payload
    assert isinstance(payload_6, (list, tuple))
    assert tuple(payload_6) == (
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


async def test_migrate_telegrams_json_missing_keys(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test migrating telegrams from legacy JSON missing fields (e.g., data_secure)."""
    store = Store[dict[str, Any]](hass, version=1, key="knx/telegrams_history.json")
    legacy_path = store.path

    legacy_data = [
        {
            "destination": "3/2/100",
            "source": "1.0.6",
            "direction": "Incoming",
            "payload": [0],
            "telegramtype": "GroupValueWrite",
            "timestamp": "2026-05-07T23:34:45.127015+02:00",
            "value": 0,
        }
    ]

    await store.async_save(legacy_data)

    await knx.setup_integration()
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams

    await hass.async_block_till_done()

    # Verify migration
    assert telegrams_module.store is not None
    result = await telegrams_module.store.query(TelegramQuery(order_descending=False))
    assert len(result.telegrams) == 1

    # Check that data_secure defaults to False/None as appropriate, and others default to None or empty string
    assert result.telegrams[0].destination == "3/2/100"
    assert result.telegrams[0].data_secure is False
    assert result.telegrams[0].source_name == ""
    assert result.telegrams[0].destination_name == ""
    assert result.telegrams[0].dpt_main is None
    assert result.telegrams[0].dpt_sub is None

    # Verify legacy file removal
    assert not os.path.exists(legacy_path)


async def test_dict_to_model_strict_key_requirements(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test that dict_to_model strictly raises KeyError if keys are missing from the dict."""
    await knx.setup_integration()
    telegrams_module = hass.data[KNX_MODULE_KEY].telegrams

    incomplete_dict: Any = {
        "destination": "3/2/100",
        "source": "1.0.6",
        "direction": "Incoming",
        "payload": [0],
        "telegramtype": "GroupValueWrite",
        "timestamp": "2026-05-07T23:34:45.127015+02:00",
        "value": 0,
        # missing data_secure, source_name, destination_name, dpt_main, dpt_sub
    }

    with pytest.raises(KeyError, match="dpt_main"):
        telegrams_module.dict_to_model(incomplete_dict)
