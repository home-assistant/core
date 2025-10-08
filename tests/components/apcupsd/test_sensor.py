"""Test sensors of APCUPSd integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.apcupsd.const import DOMAIN
from homeassistant.components.apcupsd.coordinator import REQUEST_REFRESH_COOLDOWN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

from . import MOCK_MINIMAL_STATUS, MOCK_STATUS

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "init_integration"
)


@pytest.fixture
def platforms() -> list[Platform]:
    """Overridden fixture to specify platforms to test."""
    return [Platform.SENSOR]


async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_request_status: AsyncMock,
) -> None:
    """Test states of sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Ensure entities are correctly assigned to device
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_request_status.return_value["SERIALNO"])}
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


async def test_state_update(
    hass: HomeAssistant,
    mock_request_status: AsyncMock,
) -> None:
    """Ensure the sensor state changes after updating the data."""
    device_slug = slugify(mock_request_status.return_value["UPSNAME"])
    state = hass.states.get(f"sensor.{device_slug}_load")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "14.0"

    mock_request_status.return_value = MOCK_STATUS | {"LOADPCT": "15.0 Percent"}
    future = utcnow() + timedelta(minutes=2)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.{device_slug}_load")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "15.0"


async def test_manual_update_entity(
    hass: HomeAssistant,
    mock_request_status: AsyncMock,
) -> None:
    """Test multiple simultaneous manual update entity via service homeassistant/update_entity.

    We should only do network call once for the multiple simultaneous update entity services.
    """
    device_slug = slugify(mock_request_status.return_value["UPSNAME"])
    # Assert the initial state of sensor.ups_load.
    state = hass.states.get(f"sensor.{device_slug}_load")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "14.0"

    # Setup HASS for calling the update_entity service.
    await async_setup_component(hass, "homeassistant", {})

    mock_request_status.return_value = MOCK_STATUS | {
        "LOADPCT": "15.0 Percent",
        "BCHARGE": "99.0 Percent",
    }
    # Now, we fast-forward the time to pass the debouncer cooldown, but put it
    # before the normal update interval to see if the manual update works.
    request_call_count_before = mock_request_status.call_count
    future = utcnow() + timedelta(seconds=REQUEST_REFRESH_COOLDOWN)
    async_fire_time_changed(hass, future)
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {
            ATTR_ENTITY_ID: [
                f"sensor.{device_slug}_load",
                f"sensor.{device_slug}_battery",
            ]
        },
        blocking=True,
    )
    # Even if we requested updates for two entities, our integration should smartly
    # group the API calls to just one.
    assert mock_request_status.call_count == request_call_count_before + 1

    # The new state should be effective.
    state = hass.states.get(f"sensor.{device_slug}_load")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "15.0"


@pytest.mark.parametrize("mock_request_status", [MOCK_MINIMAL_STATUS], indirect=True)
async def test_sensor_unknown(
    hass: HomeAssistant,
    mock_request_status: AsyncMock,
) -> None:
    """Test if our integration can properly mark certain sensors as unknown when it becomes so."""
    ups_mode_id = "sensor.apc_ups_mode"
    last_self_test_id = "sensor.apc_ups_last_self_test"

    assert hass.states.get(ups_mode_id).state == MOCK_MINIMAL_STATUS["UPSMODE"]
    # Last self test sensor should be added even if our status does not report it initially (it is
    # a sensor that appears only after a periodical or manual self test is performed).
    assert hass.states.get(last_self_test_id) is not None
    assert hass.states.get(last_self_test_id).state == STATE_UNKNOWN

    # Simulate an event (a self test) such that "LASTSTEST" field is being reported, the state of
    # the sensor should be properly updated with the corresponding value.
    mock_request_status.return_value = MOCK_MINIMAL_STATUS | {
        "LASTSTEST": "1970-01-01 00:00:00 0000"
    }
    future = utcnow() + timedelta(minutes=2)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert hass.states.get(last_self_test_id).state == "1970-01-01 00:00:00 0000"

    # Simulate another event (e.g., daemon restart) such that "LASTSTEST" is no longer reported.
    mock_request_status.return_value = MOCK_MINIMAL_STATUS
    future = utcnow() + timedelta(minutes=2)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    # The state should become unknown again.
    assert hass.states.get(last_self_test_id).state == STATE_UNKNOWN
