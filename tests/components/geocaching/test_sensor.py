"""Test the Geocaching sensor platform."""

import datetime as dt
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from geocachingapi.models import GeocachingCache, GeocachingStatus
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.geocaching.const import (
    DOMAIN,
    SUBENTRY_TYPE_TRACKED_CACHE,
)
from homeassistant.components.geocaching.coordinator import GeocachingCoordinatorData
from homeassistant.components.geocaching.sensor import CACHE_SENSORS, PROFILE_SENSORS
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_CODE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


async def _async_setup_geocaching_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, status: GeocachingStatus
) -> None:
    """Set up a Geocaching config entry with mocked API data."""
    session = MagicMock()
    session.token = {"access_token": "mock-token"}

    with (
        patch(
            "homeassistant.components.geocaching.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.geocaching.OAuth2Session",
            return_value=session,
        ),
        patch(
            "homeassistant.components.geocaching.coordinator.GeocachingApi"
        ) as geocaching_api_mock,
    ):
        geocaching_api_mock.return_value.update = AsyncMock(return_value=status)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_entities_are_linked_to_subentries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test entities are linked to their matching config subentries."""
    cache_code = "GC12345"
    cache_subentry_id = "cache-subentry"
    missing_cache_code = "GC99999"
    config_entry = MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={"id": "mock_user", "auth_implementation": DOMAIN},
        unique_id="mock_user",
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_CODE: cache_code},
                subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
                title=cache_code,
                unique_id=cache_code,
                subentry_id=cache_subentry_id,
            ),
            ConfigSubentryDataWithId(
                data={CONF_CODE: missing_cache_code},
                subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
                title=missing_cache_code,
                unique_id=missing_cache_code,
                subentry_id="missing-cache-subentry",
            ),
        ],
    )
    config_entry.add_to_hass(hass)

    owner = MagicMock()
    owner.username = "CacheOwner"
    cache = GeocachingCache(
        reference_code="gc12345",
        name="Test cache",
        owner=owner,
        favorite_points=10,
    )
    status = GeocachingStatus()
    status.user.username = "mock_user"
    status.user.reference_code = "PR12345"
    status.tracked_caches = [cache]

    session = MagicMock()
    session.token = {"access_token": "mock-token"}

    with (
        patch(
            "homeassistant.components.geocaching.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.geocaching.OAuth2Session",
            return_value=session,
        ),
        patch(
            "homeassistant.components.geocaching.coordinator.GeocachingApi"
        ) as geocaching_api_mock,
    ):
        geocaching_api_mock.return_value.update = AsyncMock(return_value=status)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    for description in CACHE_SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"PR12345_{cache_code}_{description.key}"
        )
        assert entity_id is not None
        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        assert entity.config_entry_id == config_entry.entry_id
        assert entity.config_subentry_id == cache_subentry_id

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"PR12345_{cache_code}_favorite_points"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "10"
    cache_entity_id = entity_id

    for description in CACHE_SENSORS:
        assert (
            entity_registry.async_get_entity_id(
                "sensor", DOMAIN, f"PR12345_{missing_cache_code}_{description.key}"
            )
            is None
        )

    for description in PROFILE_SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"PR12345_{description.key}"
        )
        assert entity_id is not None
        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        assert entity.config_entry_id == config_entry.entry_id
        assert entity.config_subentry_id is None

    cache_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, cache_code), config_entry.entry_id
    )
    assert cache_device is not None
    coordinator = config_entry.runtime_data
    updated_cache = GeocachingCache(
        reference_code=cache_code,
        name="Test cache",
        owner=owner,
        favorite_points=20,
    )
    coordinator.async_set_updated_data(
        GeocachingCoordinatorData(
            user=status.user,
            nearby_caches=status.nearby_caches,
            tracked_caches={cache_code: updated_cache},
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(cache_entity_id)
    assert state is not None
    assert state.state == "20"
    coordinator.async_set_updated_data(
        GeocachingCoordinatorData(
            user=status.user,
            nearby_caches=status.nearby_caches,
            tracked_caches={},
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(cache_entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    coordinator.data = None
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(cache_entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_same_cache_can_be_tracked_by_multiple_accounts(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the same cache has separate entities and values for each account."""
    cache_code = "GC12345"
    owner = MagicMock()
    owner.username = "CacheOwner"
    accounts = (
        ("PR12345", "first_user", 10, 1, dt.datetime(2024, 1, 2)),
        ("PR67890", "second_user", 20, 2, dt.datetime(2025, 1, 2)),
    )
    config_entries = []

    for reference_code, username, favorite_points, find_count, found_date in accounts:
        config_entry = MockConfigEntry(
            title=username,
            domain=DOMAIN,
            data={"id": username, "auth_implementation": DOMAIN},
            unique_id=username,
            subentries_data=[
                ConfigSubentryDataWithId(
                    data={CONF_CODE: cache_code},
                    subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
                    title=cache_code,
                    unique_id=cache_code,
                    subentry_id=f"{username}-cache",
                ),
            ],
        )
        config_entry.add_to_hass(hass)

        status = GeocachingStatus()
        status.user.username = username
        status.user.reference_code = reference_code
        status.user.find_count = find_count
        status.tracked_caches = [
            GeocachingCache(
                reference_code=cache_code,
                name="Test cache",
                owner=owner,
                favorite_points=favorite_points,
                found_date_time=found_date,
            )
        ]
        await _async_setup_geocaching_entry(hass, config_entry, status)
        config_entries.append(config_entry)

    found_date_entity_ids = []
    for (
        reference_code,
        _username,
        favorite_points,
        find_count,
        found_date,
    ), config_entry in zip(accounts, config_entries, strict=True):
        cache_entity_ids = []
        for description in CACHE_SENSORS:
            entity_id = entity_registry.async_get_entity_id(
                "sensor",
                DOMAIN,
                f"{reference_code}_{cache_code}_{description.key}",
            )
            assert entity_id is not None
            entity = entity_registry.async_get(entity_id)
            assert entity is not None
            assert entity.config_entry_id == config_entry.entry_id
            assert entity.config_subentry_id == f"{config_entry.unique_id}-cache"
            cache_entity_ids.append(entity_id)

        assert len(set(cache_entity_ids)) == len(CACHE_SENSORS)
        found_date_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{reference_code}_{cache_code}_found_date"
        )
        assert found_date_entity_id is not None
        found_date_entity_ids.append(found_date_entity_id)
        state = hass.states.get(found_date_entity_id)
        assert state is not None
        assert state.state == found_date.isoformat()

        favorite_points_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{reference_code}_{cache_code}_favorite_points"
        )
        assert favorite_points_entity_id is not None
        state = hass.states.get(favorite_points_entity_id)
        assert state is not None
        assert state.state == str(favorite_points)

        profile_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{reference_code}_find_count"
        )
        assert profile_entity_id is not None
        state = hass.states.get(profile_entity_id)
        assert state is not None
        assert state.state == str(find_count)

    assert len(set(found_date_entity_ids)) == 2
    cache_devices = [
        device_registry.async_get_device_by_identifier(
            (DOMAIN, cache_code), config_entry.entry_id
        )
        for config_entry in config_entries
    ]
    assert cache_devices[0] is not None
    assert cache_devices[1] is not None
    assert cache_devices[0].id != cache_devices[1].id


async def test_entities_added_when_available_after_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test configured caches missing at setup get entities later."""
    cache_code = "GC12345"
    cache_subentry_id = "cache-subentry"
    config_entry = MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={"id": "mock_user", "auth_implementation": DOMAIN},
        unique_id="mock_user",
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_CODE: cache_code},
                subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
                title=cache_code,
                unique_id=cache_code,
                subentry_id=cache_subentry_id,
            ),
        ],
    )
    config_entry.add_to_hass(hass)

    status = GeocachingStatus()
    status.user.username = "mock_user"
    status.user.reference_code = "PR12345"
    status.tracked_caches = []

    await _async_setup_geocaching_entry(hass, config_entry, status)

    for description in CACHE_SENSORS:
        assert (
            entity_registry.async_get_entity_id(
                "sensor", DOMAIN, f"PR12345_{cache_code}_{description.key}"
            )
            is None
        )
    owner = MagicMock()
    owner.username = "CacheOwner"
    cache = GeocachingCache(
        reference_code=cache_code,
        name="Test cache",
        owner=owner,
        favorite_points=10,
    )
    coordinator = config_entry.runtime_data
    coordinator.async_set_updated_data(
        GeocachingCoordinatorData(
            user=status.user,
            nearby_caches=[],
            tracked_caches={cache_code: cache},
        )
    )
    await hass.async_block_till_done()

    cache_entity_ids = []
    for description in CACHE_SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"PR12345_{cache_code}_{description.key}"
        )
        assert entity_id is not None
        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        assert entity.config_subentry_id == cache_subentry_id
        cache_entity_ids.append(entity_id)

    entities_before = {
        entity.entity_id
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
    }

    # A later refresh with the same data must not create duplicate entities.
    coordinator.async_set_updated_data(
        GeocachingCoordinatorData(
            user=status.user,
            nearby_caches=[],
            tracked_caches={cache_code: cache},
        )
    )
    await hass.async_block_till_done()

    entities_after = {
        entity.entity_id
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
    }
    assert entities_after == entities_before
    for entity_id in cache_entity_ids:
        assert entity_id in entities_after


async def test_listener_handles_missing_coordinator_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the entity-adding listener tolerates coordinator.data being None."""
    cache_code = "GC12345"
    missing_cache_code = "GC99999"
    config_entry = MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={"id": "mock_user", "auth_implementation": DOMAIN},
        unique_id="mock_user",
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_CODE: cache_code},
                subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
                title=cache_code,
                unique_id=cache_code,
                subentry_id="cache-subentry",
            ),
            ConfigSubentryDataWithId(
                data={CONF_CODE: missing_cache_code},
                subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
                title=missing_cache_code,
                unique_id=missing_cache_code,
                subentry_id="missing-cache-subentry",
            ),
        ],
    )
    config_entry.add_to_hass(hass)

    owner = MagicMock()
    owner.username = "CacheOwner"
    cache = GeocachingCache(
        reference_code=cache_code,
        name="Test cache",
        owner=owner,
        favorite_points=10,
    )
    status = GeocachingStatus()
    status.user.username = "mock_user"
    status.user.reference_code = "PR12345"
    status.tracked_caches = [cache]

    await _async_setup_geocaching_entry(hass, config_entry, status)

    cache_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"PR12345_{cache_code}_favorite_points"
    )
    assert cache_entity_id is not None
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"PR12345_{missing_cache_code}_favorite_points"
        )
        is None
    )
    coordinator = config_entry.runtime_data
    coordinator.data = None

    # Invoke our listener directly (bypassing the other, unrelated
    # coordinator listeners entities register) so this test isolates its
    # behavior specifically, per finding B.
    tracked_entities_listener = next(
        callback
        for callback, _ in coordinator._listeners.values()
        if callback.__name__ == "_async_add_tracked_entities"
    )
    caplog.clear()
    with caplog.at_level(logging.ERROR):
        tracked_entities_listener()
        await hass.async_block_till_done()

    assert not caplog.records

    # Existing entities are untouched, and nothing was created for the
    # codes that were still missing when the data disappeared.
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"PR12345_{cache_code}_favorite_points"
        )
        == cache_entity_id
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"PR12345_{missing_cache_code}_favorite_points"
        )
        is None
    )


async def test_profile_sensors_unavailable_without_coordinator_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test profile sensors become unavailable when coordinator data is missing."""
    config_entry = MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={"id": "mock_user", "auth_implementation": DOMAIN},
        unique_id="mock_user",
    )
    config_entry.add_to_hass(hass)

    status = GeocachingStatus()
    status.user.username = "mock_user"
    status.user.reference_code = "PR12345"
    await _async_setup_geocaching_entry(hass, config_entry, status)

    coordinator = config_entry.runtime_data
    coordinator.data = None
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    for description in PROFILE_SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"PR12345_{description.key}"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE
