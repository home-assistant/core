"""Test diagnostics of LaCrosse View."""
from unittest.mock import patch

from homeassistant.components.lacrosse_view import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_ENTRY_DATA, TEST_SENSOR

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test config entry diagnostics."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    with patch("lacrosse_view.LaCrosse.login", return_value=True), patch(
        "lacrosse_view.LaCrosse.get_sensors", return_value=[TEST_SENSOR]
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result["entry"]["data"] == {
        "username": "**REDACTED**",
        "password": "**REDACTED**",
        "id": "1",
        "name": "Test",
    }
    assert result["coordinator_data"] == [
        {
            "__type": "<class 'lacrosse_view.Sensor'>",
            "repr": "Sensor(name='Test', device_id='1', type='Test', sensor_id='2', sensor_field_names=['Temperature'], location=Location(id='1', name='Test'), permissions={'read': True}, model='Test', data={'Temperature': {'values': [{'s': '2'}], 'unit': 'degrees_celsius'}})",
        }
    ]
