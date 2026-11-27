"""Test the Geocaching sensor platform."""

import datetime as dt
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from geocachingapi.exceptions import GeocachingApiError
from geocachingapi.models import GeocachingUser
import pytest
from pytest_homeassistant.common import async_fire_time_changed, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.geocaching import coordinator as geocaching_coordinator
from homeassistant.components.geocaching.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.components.geocaching.coordinator import GeocachingCoordinatorData
from homeassistant.components.geocaching.sensor import (
    CACHE_SENSORS,
    PROFILE_SENSORS,
    GeocachingProfileSensor,
    GeoEntityCacheSensorEntity,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    DEFAULT_CACHE_CODE,
    DEFAULT_REFERENCE_CODE,
    DEFAULT_USERNAME,
    create_cache,
    create_config_entry,
    create_status,
    create_tracked_cache_subentry,
    setup_integration,
)


@pytest.mark.usefixtures("mock_oauth_session")
async def test_entities_are_linked_to_subentries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mock_geocaching_api: MagicMock,
) -> None:
    """Test entities are linked to their matching config subentries."""
    missing_cache_code = "GC99999"
    config_entry = create_config_entry(
        subentries=[
            create_tracked_cache_subentry(
                DEFAULT_CACHE_CODE, subentry_id="cache-subentry"
            ),
            create_tracked_cache_subentry(
                missing_cache_code, subentry_id="missing-cache-subentry"
            ),
        ]
    )
    # A lowercase reference code from the API exercises the coordinator's
    # code normalization, which must match the uppercased subentry code.
    mock_geocaching_api.update.return_value = create_status(
        tracked_caches=[create_cache(reference_code=DEFAULT_CACHE_CODE.lower())]
    )

    await setup_integration(hass, config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    # config_subentry_id is redacted to <ANY> by the snapshot serializer, so
    # the actual subentry linkage is verified explicitly here instead.
    for description in CACHE_SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            f"{DEFAULT_REFERENCE_CODE}_{DEFAULT_CACHE_CODE}_{description.key}",
        )
        assert entity_id is not None
        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        assert entity.config_entry_id == config_entry.entry_id
        assert entity.config_subentry_id == "cache-subentry"

        assert (
            entity_registry.async_get_entity_id(
                "sensor",
                DOMAIN,
                f"{DEFAULT_REFERENCE_CODE}_{missing_cache_code}_{description.key}",
            )
            is None
        )

    for description in PROFILE_SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{DEFAULT_REFERENCE_CODE}_{description.key}"
        )
        assert entity_id is not None
        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        assert entity.config_entry_id == config_entry.entry_id
        assert entity.config_subentry_id is None

    cache_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEFAULT_CACHE_CODE), config_entry.entry_id
    )
    assert cache_device is not None


@pytest.mark.usefixtures("mock_oauth_session")
async def test_cache_sensor_updates_and_becomes_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_geocaching_api: MagicMock,
) -> None:
    """Test a cache sensor reflects refreshed data and becomes unavailable."""
    config_entry = create_config_entry(
        subentries=[create_tracked_cache_subentry(DEFAULT_CACHE_CODE)]
    )
    mock_geocaching_api.update.return_value = create_status(
        tracked_caches=[create_cache(favorite_points=10)]
    )

    await setup_integration(hass, config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{DEFAULT_REFERENCE_CODE}_{DEFAULT_CACHE_CODE}_favorite_points",
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "10"

    mock_geocaching_api.update.return_value = create_status(
        tracked_caches=[create_cache(favorite_points=20)]
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "20"

    mock_geocaching_api.update.return_value = create_status(tracked_caches=[])
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_oauth_session")
async def test_cache_sensor_unavailable_after_failed_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_geocaching_api: MagicMock,
) -> None:
    """Test entities become unavailable after a failed update, then recover.

    Unlike the batch-omission scenario covered by
    test_cache_entities_appear_once_api_includes_tracked_cache, a fully
    failed update (e.g. a connection error or an exhausted rate-limit
    retry, which surface as GeocachingApiError) fails the whole refresh.
    The coordinator keeps its previous data, but CoordinatorEntity.available
    still turns False, so entities report unavailable until a refresh
    succeeds again.
    """
    config_entry = create_config_entry(
        subentries=[create_tracked_cache_subentry(DEFAULT_CACHE_CODE)]
    )
    mock_geocaching_api.update.return_value = create_status(
        tracked_caches=[create_cache(favorite_points=10)]
    )

    await setup_integration(hass, config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{DEFAULT_REFERENCE_CODE}_{DEFAULT_CACHE_CODE}_favorite_points",
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "10"

    mock_geocaching_api.update.side_effect = GeocachingApiError("boom")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_geocaching_api.update.side_effect = None
    mock_geocaching_api.update.return_value = create_status(
        tracked_caches=[create_cache(favorite_points=10)]
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "10"


@pytest.mark.usefixtures("mock_oauth_session")
async def test_same_cache_can_be_tracked_by_multiple_accounts(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_geocaching_api: MagicMock,
) -> None:
    """Test the same cache has separate entities and values for each account."""
    accounts = (
        ("PR12345", "first_user", 10, 1, dt.datetime(2024, 1, 2)),
        ("PR67890", "second_user", 20, 2, dt.datetime(2025, 1, 2)),
    )
    config_entries = []

    for reference_code, username, favorite_points, find_count, found_date in accounts:
        config_entry = create_config_entry(
            username=username,
            subentries=[
                create_tracked_cache_subentry(
                    DEFAULT_CACHE_CODE, subentry_id=f"{username}-cache"
                )
            ],
        )
        mock_geocaching_api.update.return_value = create_status(
            username=username,
            reference_code=reference_code,
            find_count=find_count,
            tracked_caches=[
                create_cache(
                    favorite_points=favorite_points, found_date_time=found_date
                )
            ],
        )
        await setup_integration(hass, config_entry)
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
                f"{reference_code}_{DEFAULT_CACHE_CODE}_{description.key}",
            )
            assert entity_id is not None
            entity = entity_registry.async_get(entity_id)
            assert entity is not None
            assert entity.config_entry_id == config_entry.entry_id
            assert entity.config_subentry_id == f"{config_entry.unique_id}-cache"
            cache_entity_ids.append(entity_id)

        assert len(set(cache_entity_ids)) == len(CACHE_SENSORS)
        found_date_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{reference_code}_{DEFAULT_CACHE_CODE}_found_date"
        )
        assert found_date_entity_id is not None
        found_date_entity_ids.append(found_date_entity_id)
        state = hass.states.get(found_date_entity_id)
        assert state is not None
        assert state.state == found_date.isoformat()

        favorite_points_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{reference_code}_{DEFAULT_CACHE_CODE}_favorite_points"
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
            (DOMAIN, DEFAULT_CACHE_CODE), config_entry.entry_id
        )
        for config_entry in config_entries
    ]
    assert cache_devices[0] is not None
    assert cache_devices[1] is not None
    assert cache_devices[0].id != cache_devices[1].id


@pytest.mark.usefixtures("mock_oauth_session")
async def test_cache_entities_appear_once_api_includes_tracked_cache(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_geocaching_api: MagicMock,
) -> None:
    """Test a configured cache gets entities once the API starts returning it.

    A batch geocaches request can succeed while omitting one of the
    requested reference codes (see GeocachingApi._update_tracked_caches,
    and the diffing logic in _verify_codes, which relies on that same
    batch behavior to detect invalid codes). This is a regression test for
    that scenario: the cache is configured from the start, but only
    resolvable by the API from a later refresh onwards. Whether such an
    omission is ever actually temporary in the real API is not established
    by this test; only the library's technical behavior is.
    """
    config_entry = create_config_entry(
        subentries=[
            create_tracked_cache_subentry(
                DEFAULT_CACHE_CODE, subentry_id="cache-subentry"
            )
        ]
    )
    mock_geocaching_api.update.return_value = create_status(tracked_caches=[])

    await setup_integration(hass, config_entry)

    for description in CACHE_SENSORS:
        assert (
            entity_registry.async_get_entity_id(
                "sensor",
                DOMAIN,
                f"{DEFAULT_REFERENCE_CODE}_{DEFAULT_CACHE_CODE}_{description.key}",
            )
            is None
        )

    mock_geocaching_api.update.return_value = create_status(
        tracked_caches=[create_cache()]
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    cache_entity_ids = []
    for description in CACHE_SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            f"{DEFAULT_REFERENCE_CODE}_{DEFAULT_CACHE_CODE}_{description.key}",
        )
        assert entity_id is not None
        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        assert entity.config_subentry_id == "cache-subentry"
        cache_entity_ids.append(entity_id)

    entities_before = {
        entity.entity_id
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
    }

    # A later refresh with the same data must not create duplicate entities.
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
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


@pytest.mark.usefixtures("mock_oauth_session")
async def test_cache_without_reference_code_is_filtered_out(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_geocaching_api: MagicMock,
) -> None:
    """Test caches without a reference code from the API are filtered out.

    GeocachingDataUpdateCoordinator normalizes each cache's reference code
    before indexing tracked_caches by it, so a cache missing one must be
    filtered out first or normalization would raise.
    """
    config_entry = create_config_entry(
        subentries=[create_tracked_cache_subentry(DEFAULT_CACHE_CODE)]
    )
    mock_geocaching_api.update.return_value = create_status(
        tracked_caches=[
            create_cache(reference_code=None),
            create_cache(reference_code=DEFAULT_CACHE_CODE, favorite_points=10),
        ]
    )

    await setup_integration(hass, config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{DEFAULT_REFERENCE_CODE}_{DEFAULT_CACHE_CODE}_favorite_points",
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "10"


@pytest.mark.parametrize(
    ("cache_codes", "expected_tracked_cache_codes"),
    [
        pytest.param({"GC12345", "GC67890"}, {"GC12345", "GC67890"}, id="configured"),
        pytest.param(set(), set(), id="not-configured"),
    ],
)
@pytest.mark.usefixtures("mock_oauth_session")
async def test_coordinator_requests_configured_cache_codes(
    hass: HomeAssistant,
    mock_geocaching_api: MagicMock,
    cache_codes: set[str],
    expected_tracked_cache_codes: set[str],
) -> None:
    """Test the coordinator asks the API for the configured tracked caches."""
    config_entry = create_config_entry(
        subentries=[create_tracked_cache_subentry(code) for code in cache_codes]
    )
    mock_geocaching_api.update.return_value = create_status()

    await setup_integration(hass, config_entry)

    settings = geocaching_coordinator.GeocachingApi.call_args.kwargs["settings"]
    assert settings.tracked_cache_codes == expected_tracked_cache_codes


def test_entities_unavailable_without_coordinator_data() -> None:
    """Test cache and profile sensors report unavailable if coordinator.data is None.

    DataUpdateCoordinator.data is typed as non-optional, but it is None
    before the first successful refresh, and both entity classes guard
    against that. This is tested directly against the entity classes,
    instead of through a running coordinator, because a coordinator never
    legitimately resets `.data` back to None again after a successful
    first refresh.
    """
    cache = create_cache()
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = GeocachingCoordinatorData(
        user=GeocachingUser(
            username=DEFAULT_USERNAME, reference_code=DEFAULT_REFERENCE_CODE
        ),
        nearby_caches=[],
        tracked_caches={DEFAULT_CACHE_CODE: cache},
    )

    cache_sensor = GeoEntityCacheSensorEntity(
        coordinator, cache, DEFAULT_CACHE_CODE, CACHE_SENSORS[0]
    )
    profile_sensor = GeocachingProfileSensor(coordinator, PROFILE_SENSORS[0])

    coordinator.data = None

    assert cache_sensor.available is False
    assert profile_sensor.available is False
