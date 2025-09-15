"""Test waze_travel_time services."""

import pytest

from homeassistant.components.waze_travel_time.const import (
    CONF_AVOID_FERRIES,
    CONF_AVOID_SUBSCRIPTION_ROADS,
    CONF_AVOID_TOLL_ROADS,
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    CONF_REALTIME,
    CONF_UNITS,
    CONF_VEHICLE_TYPE,
    DEFAULT_AVOID_FERRIES,
    DEFAULT_AVOID_SUBSCRIPTION_ROADS,
    DEFAULT_AVOID_TOLL_ROADS,
    DEFAULT_FILTER,
    DEFAULT_OPTIONS,
    DEFAULT_REALTIME,
    DEFAULT_VEHICLE_TYPE,
    DOMAIN,
    METRIC_UNITS,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_service_get_travel_times(hass: HomeAssistant) -> None:
    """Test service get_travel_times."""
    response_data = await hass.services.async_call(
        "waze_travel_time",
        "get_travel_times",
        {
            "origin": "location1",
            "destination": "location2",
            "vehicle_type": "car",
            "region": "us",
            "units": "imperial",
            "incl_filter": ["IncludeThis"],
        },
        blocking=True,
        return_response=True,
    )
    assert response_data == {
        "routes": [
            {
                "distance": pytest.approx(186.4113),
                "duration": 150,
                "name": "E1337 - Teststreet",
                "street_names": ["E1337", "IncludeThis", "Teststreet"],
            },
        ]
    }


@pytest.mark.usefixtures("mock_update")
async def test_migrate_entry_v1_v2(hass: HomeAssistant) -> None:
    """Test successful migration of entry data."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data=MOCK_CONFIG,
        options={
            CONF_REALTIME: DEFAULT_REALTIME,
            CONF_VEHICLE_TYPE: DEFAULT_VEHICLE_TYPE,
            CONF_UNITS: METRIC_UNITS,
            CONF_AVOID_FERRIES: DEFAULT_AVOID_FERRIES,
            CONF_AVOID_SUBSCRIPTION_ROADS: DEFAULT_AVOID_SUBSCRIPTION_ROADS,
            CONF_AVOID_TOLL_ROADS: DEFAULT_AVOID_TOLL_ROADS,
        },
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)

    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.version == 3
    assert updated_entry.options[CONF_INCL_FILTER] == DEFAULT_FILTER
    assert updated_entry.options[CONF_EXCL_FILTER] == DEFAULT_FILTER

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data=MOCK_CONFIG,
        options={
            CONF_REALTIME: DEFAULT_REALTIME,
            CONF_VEHICLE_TYPE: DEFAULT_VEHICLE_TYPE,
            CONF_UNITS: METRIC_UNITS,
            CONF_AVOID_FERRIES: DEFAULT_AVOID_FERRIES,
            CONF_AVOID_SUBSCRIPTION_ROADS: DEFAULT_AVOID_SUBSCRIPTION_ROADS,
            CONF_AVOID_TOLL_ROADS: DEFAULT_AVOID_TOLL_ROADS,
            CONF_INCL_FILTER: "IncludeThis",
            CONF_EXCL_FILTER: "ExcludeThis",
        },
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)

    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.version == 3
    assert updated_entry.options[CONF_INCL_FILTER] == ["IncludeThis"]
    assert updated_entry.options[CONF_EXCL_FILTER] == ["ExcludeThis"]


@pytest.mark.usefixtures("mock_update")
async def test_migrate_entry_v2_v3(hass: HomeAssistant) -> None:
    """Test v2->v3 migration renames main sensor with '_duration' suffix."""
    entry_id = "waze_entry_id"
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        entry_id=entry_id,
        unique_id=entry_id,
        data=MOCK_CONFIG,
        options={
            CONF_REALTIME: DEFAULT_REALTIME,
            CONF_VEHICLE_TYPE: DEFAULT_VEHICLE_TYPE,
            CONF_UNITS: METRIC_UNITS,
            CONF_AVOID_FERRIES: DEFAULT_AVOID_FERRIES,
            CONF_AVOID_SUBSCRIPTION_ROADS: DEFAULT_AVOID_SUBSCRIPTION_ROADS,
            CONF_AVOID_TOLL_ROADS: DEFAULT_AVOID_TOLL_ROADS,
            CONF_INCL_FILTER: None,
            CONF_EXCL_FILTER: None,
        },
    )

    mock_entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)

    old_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        mock_entry.unique_id,
        suggested_object_id="waze_travel_time",
        config_entry=mock_entry,
    )
    assert old_entity.entity_id == "sensor.waze_travel_time"

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.version == 3

    old_unique_id = mock_entry.unique_id
    new_unique_id = f"{old_unique_id}_duration"

    new_entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, new_unique_id)
    assert new_entity_id == f"{old_entity.entity_id}_duration"
