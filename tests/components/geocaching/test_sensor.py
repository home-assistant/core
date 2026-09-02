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
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_CODE, STATE_UNAVAILABLE
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


async def test_entities_are_linked_to_subentries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
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
        reference_code=" tb12345 ",
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
        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        assert entity.config_entry_id == config_entry.entry_id
        assert entity.config_subentry_id == cache_subentry_id

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{cache_code}_favorite_points"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "10"
    cache_entity_id = entity_id

    for description in TRACKABLE_SENSORS:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"PR12345_{trackable_code}_{description.key}"
        )
        assert entity_id is not None
        entity = entity_registry.async_get(entity_id)
        assert entity is not None
        assert entity.config_entry_id == config_entry.entry_id
        assert entity.config_subentry_id is None
        assert (
            entity_registry.async_get_entity_id(
                "sensor", DOMAIN, f"PR12345_TB99999_{description.key}"
            )
            is not None
        )
    trackable_entity_id = entity_id
    state = hass.states.get(trackable_entity_id)
    assert state is not None
    assert state.state == "10.5"

    for description in CACHE_SENSORS:
        assert (
            entity_registry.async_get_entity_id(
                "sensor", DOMAIN, f"{missing_cache_code}_{description.key}"
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
    trackable_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"PR12345_{trackable_code}"), config_entry.entry_id
    )
    assert trackable_device is not None

    coordinator = config_entry.runtime_data
    updated_cache = GeocachingCache(
        reference_code=cache_code,
        name="Test cache",
        owner=owner,
        favorite_points=20,
    )
    updated_trackable = GeocachingTrackable(
        reference_code=trackable_code,
        name="Test trackable",
        owner=owner,
        kilometers_traveled=20.5,
    )
    coordinator.async_set_updated_data(
        GeocachingCoordinatorData(
            user=status.user,
            trackables={trackable_code: updated_trackable},
            nearby_caches=status.nearby_caches,
            tracked_caches={cache_code: updated_cache},
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(cache_entity_id)
    assert state is not None
    assert state.state == "20"
    state = hass.states.get(trackable_entity_id)
    assert state is not None
    assert state.state == "20.5"

    coordinator.async_set_updated_data(
        GeocachingCoordinatorData(
            user=status.user,
            trackables={},
            nearby_caches=status.nearby_caches,
            tracked_caches={},
        )
    )
    await hass.async_block_till_done()

    for entity_id in (cache_entity_id, trackable_entity_id):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE

    coordinator.data = None
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    for entity_id in (cache_entity_id, trackable_entity_id):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE


async def test_entities_are_unique_per_account(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test entities and devices are unique per Geocaching account."""
    trackable_code = "TB12345"
    entries: list[tuple[MockConfigEntry, str]] = []

    for account_reference_code, entry_id in (
        ("PR11111", "entry-one"),
        ("PR22222", "entry-two"),
    ):
        config_entry = MockConfigEntry(
            title=account_reference_code,
            domain=DOMAIN,
            data={"id": entry_id, "auth_implementation": DOMAIN},
            entry_id=entry_id,
            unique_id=entry_id,
        )
        config_entry.add_to_hass(hass)

        owner = MagicMock()
        owner.username = "CacheOwner"
        trackable = GeocachingTrackable(
            reference_code=trackable_code,
            name="Test trackable",
            owner=owner,
            kilometers_traveled=10.5,
        )
        status = GeocachingStatus()
        status.user.username = entry_id
        status.user.reference_code = account_reference_code
        status.trackables = {trackable_code: trackable}

        await _async_setup_geocaching_entry(hass, config_entry, status)
        entries.append((config_entry, account_reference_code))

    trackable_devices = []
    for config_entry, account_reference_code in entries:
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

        trackable_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{account_reference_code}_{trackable_code}"),
            config_entry.entry_id,
        )
        assert trackable_device is not None
        trackable_devices.append(trackable_device)

    assert trackable_devices[0].id != trackable_devices[1].id
