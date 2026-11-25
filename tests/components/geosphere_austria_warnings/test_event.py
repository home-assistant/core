"""Tests for the GeoSphere Austria Warnings event entity."""

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pygeosphere_warnings import LocationWarnings
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.geosphere_austria_warnings.const import DOMAIN
from homeassistant.components.geosphere_austria_warnings.coordinator import (
    UPDATE_INTERVAL,
)
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

WARNING_EVENT_ENTITY_ID = "event.schwechat_warning"

pytestmark = pytest.mark.freeze_time("2023-03-27 12:00:00+02:00")


@pytest.fixture(autouse=True)
def event_platform_only() -> Generator[None]:
    """Only set up the event platform."""
    with patch(
        "homeassistant.components.geosphere_austria_warnings.PLATFORMS",
        [Platform.EVENT],
    ):
        yield


def _warnings_fixture() -> dict[str, Any]:
    """Return the raw warnings fixture."""
    return load_json_object_fixture("get_warnings_for_coords.json", DOMAIN)


async def _publish_warnings(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    data: dict[str, Any],
) -> None:
    """Publish new warning data and let the coordinator pick it up."""
    mock_client.get_last_modified.return_value = datetime(
        2023, 3, 27, 10, 0, tzinfo=UTC
    )
    mock_client.get_warnings_for_coords.return_value = LocationWarnings.from_api(data)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_client")
async def test_event_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that warnings known at setup do not fire an event."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_event_on_issued_warning(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a newly issued warning fires an event with its texts."""
    await setup_integration(hass, mock_config_entry)

    data = _warnings_fixture()
    data["properties"]["warnings"].append(
        {
            "type": "Warning",
            "properties": {
                "warnid": 5000,
                "chgid": 1,
                "verlaufid": 99,
                "warntypid": 5,
                "warnstufeid": 1,
                "create": "2023-03-27 09:55:00+00",
                "text": "Yellow thunderstorm warning",
                "auswirkungen": "* Local flooding is possible.",
                "empfehlungen": "* Seek shelter in buildings.",
                "meteotext": "Isolated thunderstorms with heavy rain.",
                "updategrund": "",
                "rawinfo": {"start": "1679911200", "end": "1679925600"},
            },
        }
    )
    await _publish_warnings(hass, mock_client, freezer, data)

    assert (state := hass.states.get(WARNING_EVENT_ENTITY_ID))
    assert state.state == "2023-03-27T10:05:00.000+00:00"
    assert state.attributes["event_type"] == "issued"
    assert state.attributes["warning_id"] == 5000
    assert state.attributes["type"] == "thunderstorm"
    assert state.attributes["level"] == "yellow"
    assert state.attributes["text"] == "Yellow thunderstorm warning"
    assert state.attributes["impacts"] == "* Local flooding is possible."
    assert state.attributes["recommendations"] == "* Seek shelter in buildings."
    assert state.attributes["meteo_text"] == "Isolated thunderstorms with heavy rain."


async def test_event_on_updated_warning(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a changed warning fires an update event."""
    await setup_integration(hass, mock_config_entry)

    data = _warnings_fixture()
    storm = data["properties"]["warnings"][1]["properties"]
    storm["chgid"] = 7
    storm["warnstufeid"] = 3
    storm["updategrund"] = "Upgraded to red."
    await _publish_warnings(hass, mock_client, freezer, data)

    assert (state := hass.states.get(WARNING_EVENT_ENTITY_ID))
    assert state.attributes["event_type"] == "updated"
    assert state.attributes["warning_id"] == 4149
    assert state.attributes["change_id"] == 7
    assert state.attributes["level"] == "red"
    assert state.attributes["update_reason"] == "Upgraded to red."


async def test_no_event_without_changes(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that refetching unchanged warnings does not fire an event."""
    await setup_integration(hass, mock_config_entry)

    await _publish_warnings(hass, mock_client, freezer, _warnings_fixture())

    assert mock_client.get_warnings_for_coords.call_count == 2
    assert (state := hass.states.get(WARNING_EVENT_ENTITY_ID))
    assert state.state == STATE_UNKNOWN
