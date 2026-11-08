"""Tests for the GeoSphere Austria Warnings services."""

import json
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pygeosphere_warnings import GeoSphereConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.geosphere_austria_warnings.const import DOMAIN
from homeassistant.components.geosphere_austria_warnings.coordinator import (
    UPDATE_INTERVAL,
)
from homeassistant.components.geosphere_austria_warnings.services import (
    SERVICE_GET_WARNINGS,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration


@pytest.mark.freeze_time("2023-03-27 12:00:00+00:00")
async def test_get_warnings_returns_both_cached_warning_buckets(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the response shape and complete warning serialization."""
    await setup_integration(hass, mock_config_entry)

    warnings_call_count = mock_client.get_warnings_for_coords.call_count
    last_modified_call_count = mock_client.get_last_modified.call_count

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_WARNINGS,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )

    assert set(response) == {"active_warnings", "advance_warnings"}
    assert len(response["active_warnings"]) == 2
    assert len(response["advance_warnings"]) == 5

    active_warning = response["active_warnings"][0]
    assert active_warning == {
        "warning_id": 4149,
        "change_id": 6,
        "course_id": 12,
        "type": "storm",
        "level": "orange",
        "start": "2023-03-27T06:00:00+00:00",
        "end": "2023-03-27T16:00:00+00:00",
        "text": "Orange storm warning from Mon, 27.03.2023 08:00 until Mon, 27.03.2023 18:00",
        "impacts": "* Branches may fall and objects may be thrown around.",
        "recommendations": "* Be careful in forests, parks and avenues!",
        "meteo_text": "Strong northwest winds with gusts between 60 and 80 km/h.",
        "update_reason": "",
    }

    advance_courses = [warning["course_id"] for warning in response["advance_warnings"]]
    assert advance_courses == [52, 31, 61, 2, 51]

    # The action uses coordinator data and does not issue another API request.
    assert mock_client.get_warnings_for_coords.call_count == warnings_call_count
    assert mock_client.get_last_modified.call_count == last_modified_call_count

    # Datetimes and enum members must not remain in the response.
    json.dumps(response)


@pytest.mark.freeze_time("2023-03-27 12:00:00+00:00")
async def test_get_warnings_after_update_failure_and_recovery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the action fails while the coordinator is unavailable."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    # A failed poll retains the old data but makes the sensors unavailable.
    mock_client.get_last_modified.side_effect = GeoSphereConnectionError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    state = hass.states.get("sensor.schwechat_active_warning_level")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_WARNINGS,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_key == "warnings_unavailable"

    # A successful poll makes both the sensor and the action available again.
    mock_client.get_last_modified.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    state = hass.states.get("sensor.schwechat_active_warning_level")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_WARNINGS,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert len(response["active_warnings"]) == 2


@pytest.mark.usefixtures("mock_client")
async def test_get_warnings_with_unloaded_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the action rejects an unloaded config entry."""
    await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_WARNINGS,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_key == "service_config_entry_not_loaded"
