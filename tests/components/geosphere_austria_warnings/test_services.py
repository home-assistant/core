"""Tests for the GeoSphere Austria Warnings services."""

import json
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.geosphere_austria_warnings.const import DOMAIN
from homeassistant.components.geosphere_austria_warnings.services import (
    ATTR_CONFIG_ENTRY,
    SERVICE_GET_WARNINGS,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry

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
        {ATTR_CONFIG_ENTRY: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )

    assert set(response) == {"active_warnings", "advance_warnings"}
    assert len(response["active_warnings"]) == 1
    assert len(response["advance_warnings"]) == 5

    active_warning = response["active_warnings"][0]
    assert active_warning == {
        "warning_id": 4149,
        "change_id": 6,
        "course_id": 12,
        "type": "storm",
        "level": "orange",
        "start": "2023-03-27T08:00:00+00:00",
        "end": "2023-03-27T18:00:00+00:00",
        "text": "Orange storm warning from Mon, 27.03.2023 08:00 until Mon, 27.03.2023 18:00",
        "impacts": "* Branches may fall and objects may be thrown around.",
        "recommendations": "* Be careful in forests, parks and avenues!",
        "meteo_text": "Strong northwest winds with gusts between 60 and 80 km/h.",
        "update_reason": "",
    }

    advance_courses = [warning["course_id"] for warning in response["advance_warnings"]]
    assert advance_courses == [52, 31, 41, 21, 61]

    # The action uses coordinator data and does not issue another API request.
    assert mock_client.get_warnings_for_coords.call_count == warnings_call_count
    assert mock_client.get_last_modified.call_count == last_modified_call_count

    # Datetimes and enum members must not remain in the response.
    json.dumps(response)


@pytest.mark.freeze_time("2023-03-27 12:00:00+00:00")
async def test_get_warnings_targets_the_selected_config_entry(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the action reads the selected config entry's coordinator."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_WARNINGS,
        {ATTR_CONFIG_ENTRY: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response["active_warnings"][0]["course_id"] == 12
