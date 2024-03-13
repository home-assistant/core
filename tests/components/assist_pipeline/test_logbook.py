"""The tests for assist_pipeline logbook."""
from homeassistant.components import assist_pipeline, logbook
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.logbook.common import MockRow, mock_humanify


async def test_recording_event(
    hass: HomeAssistant, init_components, device_registry: dr.DeviceRegistry
) -> None:
    """Test recording event."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})

    entry = MockConfigEntry()
    entry.add_to_hass(hass)
    satellite_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("demo", "satellite-1234")},
    )

    device_registry.async_update_device(satellite_device.id, name="My Satellite")
    event = mock_humanify(
        hass,
        [
            MockRow(
                assist_pipeline.EVENT_RECORDING,
                {ATTR_DEVICE_ID: satellite_device.id},
            ),
        ],
    )[0]

    assert event[logbook.LOGBOOK_ENTRY_NAME] == "My Satellite"
    assert event[logbook.LOGBOOK_ENTRY_DOMAIN] == assist_pipeline.DOMAIN
    assert (
        event[logbook.LOGBOOK_ENTRY_MESSAGE] == "My Satellite captured an audio sample"
    )
