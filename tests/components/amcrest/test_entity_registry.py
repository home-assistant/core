"""Integration-level tests for entity registry unique ID behaviour."""

from typing import Any
from unittest.mock import patch

from amcrest import AmcrestError
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    CAMERA_CONFIG,
    SERIAL_NUMBER,
    STORAGE_KEY,
    _MockAmcrestAPI,
    stored_serials,
)

# Default camera name produced by the amcrest config schema when no `name` key
# is supplied in CAMERA_CONFIG.
_DEFAULT_CAMERA_NAME = "Amcrest Camera"

# The entities CAMERA_CONFIG produces: domain, object id, the unique_id suffix
# appended to the camera's serial number, and the registered original name.
_ENTITIES = [
    ("camera", "amcrest_camera", "0-0", _DEFAULT_CAMERA_NAME),
    ("binary_sensor", "amcrest_camera_online", "online-0", "Amcrest Camera Online"),
    (
        "binary_sensor",
        "amcrest_camera_motion_detected",
        "motion_detected_polled-0",
        "Amcrest Camera Motion Detected",
    ),
    (
        "sensor",
        "amcrest_camera_ptz_preset",
        "ptz_preset-0",
        "Amcrest Camera PTZ Preset",
    ),
    ("sensor", "amcrest_camera_sd_used", "sdcard-0", "Amcrest Camera SD Used"),
    (
        "switch",
        "amcrest_camera_privacy_mode",
        "privacy_mode-0",
        "Amcrest Camera Privacy Mode",
    ),
]


def _make_unreachable(mock_api: _MockAmcrestAPI) -> None:
    """Make every call the entities use during setup fail, as an offline camera would."""
    mock_api.available = False
    mock_api.set_error("serial_number", AmcrestError("offline"))
    mock_api.set_error("current_time", AmcrestError("offline"))
    mock_api.set_error("event_channels_happened", AmcrestError("offline"))
    mock_api.set_error("ptz_presets_count", AmcrestError("offline"))
    mock_api.set_error("storage_all", AmcrestError("offline"))
    mock_api.set_error("privacy_config", AmcrestError("offline"))
    mock_api.set_error("vendor_information", AmcrestError("offline"))


def _seed_previous_run(entity_registry: er.EntityRegistry, serial: str) -> list[str]:
    """Register the entities a previous run with a reachable camera would have left."""
    return [
        entity_registry.async_get_or_create(
            domain,
            "amcrest",
            f"{serial}-{suffix}",
            suggested_object_id=object_id,
            original_name=original_name,
        ).entity_id
        for domain, object_id, suffix, original_name in _ENTITIES
    ]


async def _setup(hass: HomeAssistant, mock_api: _MockAmcrestAPI) -> None:
    """Run a full setup of the amcrest integration against the mock API."""
    with patch(
        "homeassistant.components.amcrest.AmcrestChecker", return_value=mock_api
    ):
        assert await async_setup_component(hass, "amcrest", CAMERA_CONFIG)
        await hass.async_block_till_done()


def _amcrest_entries(entity_registry: er.EntityRegistry) -> list[er.RegistryEntry]:
    """Return every amcrest entry currently in the registry."""
    return [
        entry
        for entry in entity_registry.entities.values()
        if entry.platform == "amcrest"
    ]


@pytest.mark.usefixtures("mock_event_monitor")
async def test_entities_registered_with_serial_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
    mock_api: _MockAmcrestAPI,
) -> None:
    """A reachable camera registers every entity against its serial number."""
    await _setup(hass, mock_api)

    entries = _amcrest_entries(entity_registry)
    assert len(entries) == len(_ENTITIES)
    for entry in entries:
        assert entry.unique_id.startswith(SERIAL_NUMBER), (
            f"{entry.entity_id!r} has unique_id {entry.unique_id!r}; "
            f"expected prefix {SERIAL_NUMBER!r}"
        )


@pytest.mark.usefixtures("mock_event_monitor")
async def test_entities_registered_when_camera_unreachable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
    mock_api: _MockAmcrestAPI,
) -> None:
    """An unreachable camera still registers every entity, against the fallback ID."""
    _make_unreachable(mock_api)

    await _setup(hass, mock_api)

    # Before the fix, an unreachable camera left unique_id unset, so none of
    # these entities reached the registry at all.
    entries = _amcrest_entries(entity_registry)
    assert len(entries) == len(_ENTITIES)
    fallback_id = hass_storage[STORAGE_KEY]["data"]["serial_numbers"][
        _DEFAULT_CAMERA_NAME
    ]
    for entry in entries:
        assert entry.unique_id.startswith(fallback_id)


@pytest.mark.usefixtures("mock_event_monitor")
async def test_entity_ids_stable_across_restart(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
    mock_api: _MockAmcrestAPI,
) -> None:
    """Entity IDs survive a restart in which the camera is unreachable."""
    previous_entity_ids = _seed_previous_run(entity_registry, SERIAL_NUMBER)
    hass_storage[STORAGE_KEY] = stored_serials({_DEFAULT_CAMERA_NAME: SERIAL_NUMBER})
    _make_unreachable(mock_api)

    await _setup(hass, mock_api)

    # Asserted against the state machine, not the registry: entities without a
    # unique_id never reach the registry, so that is where the duplicates land.
    live_entity_ids = hass.states.async_entity_ids()
    assert sorted(live_entity_ids) == sorted(previous_entity_ids)
    assert not any("_2" in entity_id for entity_id in live_entity_ids), (
        f"Unexpected _2 suffix: {sorted(live_entity_ids)}"
    )


@pytest.mark.usefixtures("mock_event_monitor")
async def test_registered_serial_reused_when_camera_unreachable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_storage: dict[str, Any],
    mock_api: _MockAmcrestAPI,
) -> None:
    """With nothing stored, an offline camera recovers its serial from the registry.

    This is the upgrade path: entities already exist under the camera's real
    serial number, but nothing has been persisted yet. Minting a UUID here would
    orphan them permanently, since the UUID is preferred on every later start.
    """
    previous_entity_ids = _seed_previous_run(entity_registry, SERIAL_NUMBER)
    _make_unreachable(mock_api)

    await _setup(hass, mock_api)

    assert hass_storage[STORAGE_KEY]["data"] == {
        "serial_numbers": {_DEFAULT_CAMERA_NAME: SERIAL_NUMBER}
    }
    entries = _amcrest_entries(entity_registry)
    assert sorted(entry.entity_id for entry in entries) == sorted(previous_entity_ids)
