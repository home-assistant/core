"""Test Brother diagnostics."""
from datetime import datetime
import json
from unittest.mock import Mock, patch

from homeassistant.util.dt import UTC

from tests.common import load_fixture
from tests.components.brother import init_integration
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, hass_client):
    """Test config entry diagnostics."""
    entry = await init_integration(hass, skip_setup=True)

    test_time = datetime(2019, 11, 11, 9, 10, 32, tzinfo=UTC)
    with patch("brother.datetime", utcnow=Mock(return_value=test_time)), patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("printer_data.json", "brother")),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    result["info"].pop("entry_id")

    assert result["info"] == {
        "data": {"host": "localhost", "type": "laser"},
        "disabled_by": None,
        "domain": "brother",
        "options": {},
        "pref_disable_new_entities": False,
        "pref_disable_polling": False,
        "source": "user",
        "title": "HL-L2340DW 0123456789",
        "unique_id": "0123456789",
        "version": 1,
    }

    assert result["data"] == {
        "b/w_counter": 709,
        "belt_unit_remaining_life": 97,
        "belt_unit_remaining_pages": 48436,
        "black_drum_counter": 1611,
        "black_drum_remaining_life": 92,
        "black_drum_remaining_pages": 16389,
        "black_toner": 80,
        "black_toner_remaining": 75,
        "black_toner_status": 1,
        "color_counter": 902,
        "cyan_drum_counter": 1611,
        "cyan_drum_remaining_life": 92,
        "cyan_drum_remaining_pages": 16389,
        "cyan_toner": 10,
        "cyan_toner_remaining": 10,
        "cyan_toner_status": 1,
        "drum_counter": 986,
        "drum_remaining_life": 92,
        "drum_remaining_pages": 11014,
        "drum_status": 1,
        "duplex_unit_pages_counter": 538,
        "firmware": "1.17",
        "fuser_remaining_life": 97,
        "laser_unit_remaining_pages": 48389,
        "magenta_drum_counter": 1611,
        "magenta_drum_remaining_life": 92,
        "magenta_drum_remaining_pages": 16389,
        "magenta_toner": 10,
        "magenta_toner_remaining": 8,
        "magenta_toner_status": 2,
        "model": "HL-L2340DW",
        "page_counter": 986,
        "pf_kit_1_remaining_life": 98,
        "pf_kit_1_remaining_pages": 48741,
        "serial": "0123456789",
        "status": "waiting",
        "uptime": "2019-09-24T12:14:56+00:00",
        "yellow_drum_counter": 1611,
        "yellow_drum_remaining_life": 92,
        "yellow_drum_remaining_pages": 16389,
        "yellow_toner": 10,
        "yellow_toner_remaining": 2,
        "yellow_toner_status": 2,
    }
