"""Test Wallbox Init Component."""
import json

from homeassistant.components.wallbox.const import CONF_STATION, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.wallbox import setup_integration

entry = MockConfigEntry(
    domain=DOMAIN,
    data={
        CONF_USERNAME: "test_username",
        CONF_PASSWORD: "test_password",
        CONF_STATION: "12345",
    },
    entry_id="testEntry",
)

test_response = json.loads(
    '{"charging_power": 0,"max_available_power": 25,"charging_speed": 0,"added_range": 372,"added_energy": 44.697}'
)

test_response_rounding_error = json.loads(
    '{"charging_power": "XX","max_available_power": "xx","charging_speed": 0,"added_range": "xx","added_energy": "XX"}'
)


async def test_wallbox_unload_entry(hass: HomeAssistant):
    """Test Wallbox Unload."""

    await setup_integration(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
