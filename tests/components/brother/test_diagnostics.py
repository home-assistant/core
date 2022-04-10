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

    diagnostics_data = json.loads(load_fixture("diagnostics_data.json", "brother"))
    test_time = datetime(2019, 11, 11, 9, 10, 32, tzinfo=UTC)
    with patch("brother.datetime", utcnow=Mock(return_value=test_time)), patch(
        "brother.Brother._get_data",
        return_value=json.loads(load_fixture("printer_data.json", "brother")),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["info"] == {"host": "localhost", "type": "laser"}
    assert result["data"] == diagnostics_data
