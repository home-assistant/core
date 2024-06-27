"""Test ViCare binary sensors."""

from unittest.mock import patch

from homeassistant.components.vicare.const import CONF_EXTENDED_API
from homeassistant.core import HomeAssistant

from . import MODULE

from tests.components.vicare.conftest import Fixture, MockPyViCare, mock_config_entry


async def test_v1_v2_migration(
    hass: HomeAssistant,
    mock_v1_config_entry: mock_config_entry,
) -> None:
    """Test the ViCare binary sensor."""
    fixtures: list[Fixture] = [Fixture({"type:boiler"}, "vicare/Vitodens300W.json")]
    with patch(
        f"{MODULE}.vicare_login",
        return_value=MockPyViCare(fixtures),
    ):
        assert mock_v1_config_entry.version == 1
        assert len(mock_v1_config_entry.options) == 0

        mock_v1_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_v1_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_v1_config_entry.version == 2
        assert len(mock_v1_config_entry.options) == 1
        assert mock_v1_config_entry.options.get(CONF_EXTENDED_API) is False
