"""The tests for the Traccar device tracker platform."""

import pytest

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    TrackerEntityStateAttribute,
)
from homeassistant.components.device_tracker.legacy import Device
from homeassistant.components.traccar import DOMAIN
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    CONF_WEBHOOK_ID,
    STATE_NOT_HOME,
    EntityStateAttribute,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_restore_cache

DEVICE_ID = "device_1"
ENTITY_ID = f"{DEVICE_TRACKER_DOMAIN}.{DEVICE_ID}"


@pytest.fixture(autouse=True)
def mock_dev_track(mock_device_tracker_conf: list[Device]) -> None:
    """Mock device tracker config loading."""


async def test_restore_state(hass: HomeAssistant) -> None:
    """Test that the previous location is restored for a known device."""
    assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, {})

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_WEBHOOK_ID: "webhook_id"})
    entry.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DEVICE_ID)},
    )

    mock_restore_cache(
        hass,
        [
            State(
                ENTITY_ID,
                STATE_NOT_HOME,
                {
                    EntityStateAttribute.LATITUDE: 1.0,
                    EntityStateAttribute.LONGITUDE: 2.0,
                    TrackerEntityStateAttribute.GPS_ACCURACY: 30,
                    ATTR_BATTERY_LEVEL: 40,
                    "altitude": 50,
                    "bearing": 60,
                    "speed": 70,
                },
            )
        ],
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[EntityStateAttribute.LATITUDE] == 1.0
    assert state.attributes[EntityStateAttribute.LONGITUDE] == 2.0
    assert state.attributes[TrackerEntityStateAttribute.GPS_ACCURACY] == 30
    assert state.attributes[ATTR_BATTERY_LEVEL] == 40
    assert state.attributes["altitude"] == 50
    assert state.attributes["bearing"] == 60
    assert state.attributes["speed"] == 70
