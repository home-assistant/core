"""Test the Geocaching sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from geocachingapi.models import GeocachingCache, GeocachingStatus, GeocachingTrackable

from homeassistant.components.geocaching.const import (
    DOMAIN,
    SUBENTRY_TYPE_TRACKED_CACHE,
)
from homeassistant.components.geocaching.coordinator import GeocachingCoordinatorData
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
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


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

    coordinator = MagicMock()
    user = MagicMock()
    user.reference_code = "PR12345"
    coordinator.data = GeocachingCoordinatorData(
        user=user,
        trackables={},
        nearby_caches=[],
        tracked_caches={"GC12345": first_cache},
    )

    description = next(
        description
        for description in CACHE_SENSORS
        if description.key == "favorite_points"
    )

    entity = GeoEntityCacheSensorEntity(
        coordinator,
        first_cache,
        "GC12345",
        description,
    )

    assert entity.available
    assert entity.unique_id == "PR12345_GC12345_favorite_points"
    assert entity.device_info["identifiers"] == {(DOMAIN, "PR12345_GC12345")}
    assert entity.native_value == 10

    updated_cache = GeocachingCache(
        reference_code="GC12345",
        name="Test cache",
        owner=owner,
        favorite_points=20,
    )

    coordinator.data = GeocachingCoordinatorData(
        user=user,
        trackables={},
        nearby_caches=[],
        tracked_caches={"GC12345": updated_cache},
    )

    assert entity.cache is updated_cache
    assert entity.native_value == 20

    coordinator.data = GeocachingCoordinatorData(
        user=user, trackables={}, nearby_caches=[], tracked_caches={}
    )
    assert not entity.available

    coordinator.last_update_success = True
    coordinator.data = None
    assert not entity.available


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

    coordinator = MagicMock()
    user = MagicMock()
    user.reference_code = "PR12345"
    coordinator.data = GeocachingCoordinatorData(
        user=user,
        trackables={"TB12345": first_trackable},
        nearby_caches=[],
        tracked_caches={},
    )

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

    assert entity.unique_id == "PR12345_TB12345_kilometers_traveled"
    assert entity.device_info["identifiers"] == {(DOMAIN, "PR12345_TB12345")}
    assert entity.native_value == 10.5

    updated_trackable = GeocachingTrackable(
        reference_code="TB12345",
        name="Test trackable",
        owner=owner,
        kilometers_traveled=20.5,
    )

    coordinator.data = GeocachingCoordinatorData(
        user=user,
        trackables={"TB12345": updated_trackable},
        nearby_caches=[],
        tracked_caches={},
    )

    assert entity.native_value == 20.5


async def test_entities_are_linked_to_subentries(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test entities are linked to their matching config subentries."""
    cache_code = "GC12345"
    trackable_code = "TB12345"
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
            "sensor", DOMAIN, f"PR12345_{cache_code}_{description.key}"
        )
        assert entity_id is not None
        assert (
            entity_registry.async_get(entity_id).config_subentry_id == cache_subentry_id
        )

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"PR12345_{cache_code}_favorite_points"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "10"

    for description in TRACKABLE_SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"PR12345_{trackable_code}_{description.key}"
        )
        assert entity_id is not None
        assert entity_registry.async_get(entity_id).config_subentry_id is None
        assert (
            entity_registry.async_get_entity_id(
                "sensor", DOMAIN, f"PR12345_TB99999_{description.key}"
            )
            is not None
        )

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
        assert entity_registry.async_get(entity_id).config_subentry_id is None


async def test_entities_are_unique_per_account(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test entities and devices are unique per Geocaching account."""
    cache_code = "GC12345"
    trackable_code = "TB12345"
    entries: list[tuple[MockConfigEntry, str, str]] = []

    for account_reference_code, entry_id in (
        ("PR11111", "entry-one"),
        ("PR22222", "entry-two"),
    ):
        subentry_id = f"cache-{entry_id}"
        config_entry = MockConfigEntry(
            title=account_reference_code,
            domain=DOMAIN,
            data={"id": entry_id, "auth_implementation": DOMAIN},
            entry_id=entry_id,
            unique_id=entry_id,
            subentries_data=[
                ConfigSubentryDataWithId(
                    data={CONF_CODE: cache_code},
                    subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
                    title=cache_code,
                    unique_id=cache_code,
                    subentry_id=subentry_id,
                )
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
        status = GeocachingStatus()
        status.user.username = entry_id
        status.user.reference_code = account_reference_code
        status.tracked_caches = [cache]
        status.trackables = {trackable_code: trackable}

        await _async_setup_geocaching_entry(hass, config_entry, status)
        entries.append((config_entry, account_reference_code, subentry_id))

    cache_devices = []
    trackable_devices = []
    for config_entry, account_reference_code, subentry_id in entries:
        for description in CACHE_SENSORS:
            unique_id = f"{account_reference_code}_{cache_code}_{description.key}"
            entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            assert entity_id is not None
            entity = entity_registry.async_get(entity_id)
            assert entity is not None
            assert entity.config_entry_id == config_entry.entry_id
            assert entity.config_subentry_id == subentry_id

        for description in TRACKABLE_SENSORS:
            unique_id = f"{account_reference_code}_{trackable_code}_{description.key}"
            entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            assert entity_id is not None
            entity = entity_registry.async_get(entity_id)
            assert entity is not None
            assert entity.config_entry_id == config_entry.entry_id
            assert entity.config_subentry_id is None

        for description in PROFILE_SENSORS:
            unique_id = f"{account_reference_code}_{description.key}"
            entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            assert entity_id is not None
            entity = entity_registry.async_get(entity_id)
            assert entity is not None
            assert entity.config_entry_id == config_entry.entry_id
            assert entity.config_subentry_id is None

        cache_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{account_reference_code}_{cache_code}"),
            config_entry.entry_id,
        )
        assert cache_device is not None
        cache_devices.append(cache_device)

        trackable_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{account_reference_code}_{trackable_code}"),
            config_entry.entry_id,
        )
        assert trackable_device is not None
        trackable_devices.append(trackable_device)

    assert cache_devices[0].id != cache_devices[1].id
    assert trackable_devices[0].id != trackable_devices[1].id
