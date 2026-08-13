"""Test the Geocaching sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from geocachingapi.models import GeocachingCache, GeocachingStatus, GeocachingTrackable

from homeassistant.components.geocaching.const import (
    DOMAIN,
    SUBENTRY_TYPE_TRACKABLE,
    SUBENTRY_TYPE_TRACKED_CACHE,
)
from homeassistant.components.geocaching.sensor import (
    CACHE_SENSORS,
    PROFILE_SENSORS,
    TRACKABLE_SENSORS,
    GeoEntityCacheSensorEntity,
    GeoEntityTrackableSensorEntity,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


def test_cache_sensor_uses_latest_coordinator_data() -> None:
    """Test that a cache sensor uses the latest coordinator data."""
    owner = MagicMock()
    owner.username = "CacheOwner"

    first_cache = GeocachingCache(
        reference_code="GC12345",
        name="Test cache",
        owner=owner,
        favorite_points=10,
    )

    first_status = GeocachingStatus()
    first_status.tracked_caches = [first_cache]

    coordinator = MagicMock()
    coordinator.data = first_status

    description = next(
        description
        for description in CACHE_SENSORS
        if description.key == "favorite_points"
    )

    entity = GeoEntityCacheSensorEntity(
        coordinator,
        first_cache,
        description,
    )

    assert entity.native_value == 10

    updated_cache = GeocachingCache(
        reference_code="GC12345",
        name="Test cache",
        owner=owner,
        favorite_points=20,
    )

    updated_status = GeocachingStatus()
    updated_status.tracked_caches = [updated_cache]

    coordinator.data = updated_status

    assert entity.native_value == 20


def test_trackable_sensor_uses_latest_coordinator_data() -> None:
    """Test that a trackable sensor uses the latest coordinator data."""
    owner = MagicMock()
    owner.username = "TrackableOwner"

    first_trackable = GeocachingTrackable(
        reference_code="TB12345",
        name="Test trackable",
        owner=owner,
        kilometers_traveled=10.5,
    )

    first_status = GeocachingStatus()
    first_status.trackables = {"TB12345": first_trackable}

    coordinator = MagicMock()
    coordinator.data = first_status

    description = next(
        description
        for description in TRACKABLE_SENSORS
        if description.key == "kilometers_traveled"
    )

    entity = GeoEntityTrackableSensorEntity(
        coordinator,
        first_trackable,
        description,
    )

    assert entity.native_value == 10.5

    updated_trackable = GeocachingTrackable(
        reference_code="TB12345",
        name="Test trackable",
        owner=owner,
        kilometers_traveled=20.5,
    )

    updated_status = GeocachingStatus()
    updated_status.trackables = {"TB12345": updated_trackable}

    coordinator.data = updated_status

    assert entity.native_value == 20.5


async def test_entities_are_linked_to_subentries(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test entities are linked to their matching config subentries."""
    cache_code = "GC12345"
    trackable_code = "TB12345"
    cache_subentry_id = "cache-subentry"
    trackable_subentry_id = "trackable-subentry"
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
                data={CONF_CODE: trackable_code},
                subentry_type=SUBENTRY_TYPE_TRACKABLE,
                title=trackable_code,
                unique_id=trackable_code,
                subentry_id=trackable_subentry_id,
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
    trackable = GeocachingTrackable(
        reference_code=trackable_code,
        name="Test trackable",
        owner=owner,
        kilometers_traveled=10.5,
    )
    unmatched_trackable = GeocachingTrackable(
        reference_code="TB99999",
        name="Unmatched trackable",
        owner=owner,
        kilometers_traveled=20.5,
    )
    status = GeocachingStatus()
    status.user.username = "mock_user"
    status.user.reference_code = "PR12345"
    status.tracked_caches = [cache]
    status.trackables = {
        trackable_code: trackable,
        "TB99999": unmatched_trackable,
    }

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
            "sensor", DOMAIN, f"{cache_code}_{description.key}"
        )
        assert entity_id is not None
        assert (
            entity_registry.async_get(entity_id).config_subentry_id == cache_subentry_id
        )

    for description in TRACKABLE_SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{trackable_code}_{description.key}"
        )
        assert entity_id is not None
        assert (
            entity_registry.async_get(entity_id).config_subentry_id
            == trackable_subentry_id
        )
        assert (
            entity_registry.async_get_entity_id(
                "sensor", DOMAIN, f"TB99999_{description.key}"
            )
            is None
        )

    for description in PROFILE_SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"PR12345_{description.key}"
        )
        assert entity_id is not None
        assert entity_registry.async_get(entity_id).config_subentry_id is None
