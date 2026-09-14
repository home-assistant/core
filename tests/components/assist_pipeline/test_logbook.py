"""The tests for assist_pipeline logbook."""

import pytest

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
    await hass.async_block_till_done()

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


@pytest.mark.usefixtures("init_components")
async def test_recording_event_child_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test recording event fired for a child device."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

    entry = MockConfigEntry()
    entry.add_to_hass(hass)
    satellite_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections=set(),
        identifiers={("demo", "satellite-1234")},
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=entry.entry_id,
        identifiers={("demo", "satellite-1234-child")},
        parent_device_id=satellite_device.id,
        name="My Child Satellite",
    )

    event = mock_humanify(
        hass,
        [
            MockRow(
                assist_pipeline.EVENT_RECORDING,
                {ATTR_DEVICE_ID: child_device.id},
            ),
        ],
    )[0]

    assert event[logbook.LOGBOOK_ENTRY_NAME] == "My Child Satellite"
    assert (
        event[logbook.LOGBOOK_ENTRY_MESSAGE]
        == "My Child Satellite captured an audio sample"
    )


@pytest.mark.usefixtures("init_components")
async def test_recording_event_unknown_device(hass: HomeAssistant) -> None:
    """Test recording event for an unknown device does not raise."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

    event = mock_humanify(
        hass,
        [
            MockRow(
                assist_pipeline.EVENT_RECORDING,
                {ATTR_DEVICE_ID: "non-existing-device"},
            ),
        ],
    )[0]

    assert event[logbook.LOGBOOK_ENTRY_NAME] == "Unknown device"
    assert (
        event[logbook.LOGBOOK_ENTRY_MESSAGE]
        == "Unknown device captured an audio sample"
    )
