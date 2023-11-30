"""Test Wyoming select."""
from homeassistant.components.assist_pipeline.select import OPTION_PREFERRED
from homeassistant.components.wyoming.devices import SatelliteDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_pipeline_select(
    hass: HomeAssistant,
    satellite_config_entry: ConfigEntry,
    satellite_device: SatelliteDevice,
) -> None:
    """Test pipeline select.

    Functionality is tested in assist_pipeline/test_select.py.
    This test is only to ensure it is set up.
    """
    pipeline_entity_id = satellite_device.get_pipeline_entity_id(hass)
    assert pipeline_entity_id

    state = hass.states.get(pipeline_entity_id)
    assert state is not None
    assert state.state == OPTION_PREFERRED
