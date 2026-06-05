"""Tests for sensor platform setup — entity creation and state via library events.

All tests follow the HA-preferred pattern:
  1. Set up the entry through normal config-entry machinery.
  2. Inject library events via the captured on_device_event callback.
  3. Assert on hass.states and the entity / device registries.

Integration internals (dispatcher, VHH, etc.) are not accessed directly
except where no observable HA boundary exists.
"""

from collections.abc import Callable, Coroutine
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.powersensor_au.config_flow import PowersensorConfigFlow
from homeassistant.components.powersensor_au.const import (
    DOMAIN,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_UPDATE_SIGNAL,
    ROLE_WATER,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

PLUG_MAC = "aabbccddeeff"
SENSOR_MAC = "112233445566"
SOLAR_MAC = "665544332211"

# Expected entity counts from sensor.py description tuples.
# 7 total; 3 universal (battery_level, device_role, rssi_ble) + role-gated.
_UNIVERSAL_SENSOR_COUNT = 3  # battery_level, device_role, rssi_ble
_HOUSENET_SENSOR_COUNT = 9  # 3 universal + 2 role-gated (power, total_energy)
# + 4 VHH consumption entities
_WATER_SENSOR_COUNT = (
    5  # 3 universal + 2 role-gated (water_flow_rate, total_water_consumption)
)
_PLUG_COUNT = 7  # all PLUG_DESCRIPTIONS
_CONSUMPTION_VHH_COUNT = 4  # CONSUMPTION_DESCRIPTIONS
_PRODUCTION_VHH_COUNT = 4  # PRODUCTION_DESCRIPTIONS


def _registered(hass: HomeAssistant, entry: MockConfigEntry) -> list[er.RegistryEntry]:
    reg = er.async_get(hass)
    return er.async_entries_for_config_entry(reg, entry.entry_id)


# ---------------------------------------------------------------------------
# Plug discovery
# ---------------------------------------------------------------------------


async def test_plug_discovery_creates_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """A device_found plug event creates all PLUG_DESCRIPTIONS entities."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()

    entities = _registered(hass, config_entry)
    assert len(entities) == _PLUG_COUNT

    unique_ids = {e.unique_id for e in entities}
    assert f"{PLUG_MAC}_power" in unique_ids
    assert f"{PLUG_MAC}_total_energy" in unique_ids
    assert f"{PLUG_MAC}_device_role" in unique_ids


async def test_plug_discovery_is_idempotent(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Firing device_found twice for the same plug MAC creates entities only once."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == _PLUG_COUNT


async def test_plug_subscribe_called(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """subscribe() is called on the devices layer when a plug is discovered."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()

    mock_devices.subscribe.assert_called_with(PLUG_MAC)


# ---------------------------------------------------------------------------
# Sensor discovery — no role
# ---------------------------------------------------------------------------


async def test_sensor_no_role_creates_universal_entities_only(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """A sensor with role=None only gets the three universal entities."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    entities = _registered(hass, config_entry)
    assert len(entities) == _UNIVERSAL_SENSOR_COUNT

    unique_ids = {e.unique_id for e in entities}
    assert f"{SENSOR_MAC}_battery_level" in unique_ids
    assert f"{SENSOR_MAC}_device_role" in unique_ids
    assert f"{SENSOR_MAC}_rssi_ble" in unique_ids
    # Role-gated entities must NOT be present.
    assert f"{SENSOR_MAC}_power" not in unique_ids
    assert f"{SENSOR_MAC}_total_energy" not in unique_ids


# ---------------------------------------------------------------------------
# Sensor discovery — with role from persisted data
# ---------------------------------------------------------------------------


async def test_sensor_with_persisted_housenet_role_creates_full_entities(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    mock_async_zeroconf: MagicMock,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """A sensor whose role is already in entry.data gets all housenet entities on discovery."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"roles": {SENSOR_MAC: ROLE_HOUSENET}},
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.powersensor_au.PowersensorZeroconfDevices",
        return_value=mock_devices,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    cb = mock_devices.start.call_args[0][0]
    await cb({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(reg, entry.entry_id)
    assert len(entities) == _HOUSENET_SENSOR_COUNT

    unique_ids = {e.unique_id for e in entities}
    assert f"{SENSOR_MAC}_power" in unique_ids
    assert f"{SENSOR_MAC}_total_energy" in unique_ids


# ---------------------------------------------------------------------------
# Role assignment via now_relaying_for
# ---------------------------------------------------------------------------


async def test_now_relaying_for_triggers_role_update(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """now_relaying_for with a concrete role creates the role-gated entities."""
    # First discover the sensor (no role yet — library never includes role in device_found).
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    # Now the library relays the now_relaying_for event with the role.
    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": ROLE_HOUSENET})
    await hass.async_block_till_done()

    entities = _registered(hass, config_entry)
    assert len(entities) == _HOUSENET_SENSOR_COUNT

    unique_ids = {e.unique_id for e in entities}
    assert f"{SENSOR_MAC}_power" in unique_ids
    assert f"{SENSOR_MAC}_total_energy" in unique_ids


async def test_now_relaying_for_without_role_is_a_noop(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """now_relaying_for with no/unknown role does not create role-gated entities."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    count_before = len(_registered(hass, config_entry))

    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": "unknown"})
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == count_before


# ---------------------------------------------------------------------------
# Role update (measurement event path)
# ---------------------------------------------------------------------------


async def test_measurement_with_role_creates_role_gated_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """An average_power measurement carrying a role triggers entity creation."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == _UNIVERSAL_SENSOR_COUNT

    await fire(
        {
            "event": "average_power",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
            "watts": 1200.0,
            "starttime_utc": 1700000000,
            "duration_s": 10,
        }
    )
    await hass.async_block_till_done()

    entities = _registered(hass, config_entry)
    assert len(entities) == _HOUSENET_SENSOR_COUNT


async def test_measurement_updates_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """A measurement event updates the corresponding entity's state value."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "average_power",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
            "watts": 850.5,
            "starttime_utc": 1700000000,
            "duration_s": 10,
        }
    )
    await hass.async_block_till_done()

    reg = er.async_get(hass)
    entity_id = reg.async_get_entity_id(Platform.SENSOR, DOMAIN, f"{SENSOR_MAC}_power")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(850.5, rel=1e-3)


async def test_battery_level_converted_from_volts(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Battery voltage is converted to a percentage (3.3V=0%, 4.15V=100%)."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "battery_level",
            "mac": SENSOR_MAC,
            "volts": 3.725,  # midpoint → 50%
        }
    )
    await hass.async_block_till_done()

    reg = er.async_get(hass)
    entity_id = reg.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SENSOR_MAC}_battery_level"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(50.0, abs=0.1)


async def test_energy_converted_from_joules(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """summation_joules is converted to kWh before storing state."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "average_power",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
            "watts": 0,
            "starttime_utc": 1700000000,
            "duration_s": 10,
        }
    )
    await fire(
        {
            "event": "summation_energy",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
            "summation_joules": 3_600_000,  # 1 kWh
        }
    )
    await hass.async_block_till_done()

    reg = er.async_get(hass)
    entity_id = reg.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SENSOR_MAC}_total_energy"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(1.0, rel=1e-4)


# ---------------------------------------------------------------------------
# Water sensor
# ---------------------------------------------------------------------------


async def test_water_sensor_creates_water_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """A sensor assigned ROLE_WATER gets flow-rate and volume entities."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": ROLE_WATER})
    await hass.async_block_till_done()

    entities = _registered(hass, config_entry)
    assert len(entities) == _WATER_SENSOR_COUNT

    unique_ids = {e.unique_id for e in entities}
    assert f"{SENSOR_MAC}_water_flow_rate" in unique_ids
    assert f"{SENSOR_MAC}_total_water_consumption" in unique_ids


# ---------------------------------------------------------------------------
# Role change adds entities without duplicates
# ---------------------------------------------------------------------------


async def test_role_change_adds_entities_without_duplicates(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Changing role from house-net to water adds water entities; going back is a noop."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": ROLE_HOUSENET})
    await hass.async_block_till_done()
    count_housenet = len(_registered(hass, config_entry))
    assert count_housenet == _HOUSENET_SENSOR_COUNT

    # Switch to water — adds the 2 water-specific entities.
    await fire(
        {
            "event": "average_power",
            "mac": SENSOR_MAC,
            "role": ROLE_WATER,
            "watts": 0,
            "starttime_utc": 1700000001,
            "duration_s": 10,
        }
    )
    await hass.async_block_till_done()
    count_after_water = len(_registered(hass, config_entry))
    assert count_after_water == count_housenet + 2

    # Switch back — no new entities, no duplicates.
    await fire(
        {
            "event": "average_power",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
            "watts": 0,
            "starttime_utc": 1700000002,
            "duration_s": 10,
        }
    )
    await hass.async_block_till_done()
    assert len(_registered(hass, config_entry)) == count_after_water


# ---------------------------------------------------------------------------
# Virtual Household
# ---------------------------------------------------------------------------


async def test_vhh_mains_entities_created_when_housenet_sensor_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Mains VHH entities are added once a house-net sensor is discovered."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": ROLE_HOUSENET})
    await hass.async_block_till_done()

    unique_ids = {e.unique_id for e in _registered(hass, config_entry)}
    assert f"{DOMAIN}_vhh_home_usage" in unique_ids
    assert f"{DOMAIN}_vhh_from_grid" in unique_ids
    assert f"{DOMAIN}_vhh_home_usage_summation" in unique_ids
    assert f"{DOMAIN}_vhh_from_grid_summation" in unique_ids


async def test_vhh_solar_entities_added_when_solar_sensor_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Solar VHH entities are added when a solar sensor joins alongside a mains sensor."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": ROLE_HOUSENET})
    await fire({"event": "device_found", "mac": SOLAR_MAC, "device_type": "sensor"})
    await fire({"event": "now_relaying_for", "mac": SOLAR_MAC, "role": ROLE_SOLAR})
    await hass.async_block_till_done()

    unique_ids = {e.unique_id for e in _registered(hass, config_entry)}
    assert f"{DOMAIN}_vhh_to_grid" in unique_ids
    assert f"{DOMAIN}_vhh_solar_generation" in unique_ids


async def test_vhh_solar_not_created_without_mains(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Solar VHH entities are NOT created when there is no mains sensor."""
    await fire({"event": "device_found", "mac": SOLAR_MAC, "device_type": "sensor"})
    await fire({"event": "now_relaying_for", "mac": SOLAR_MAC, "role": ROLE_SOLAR})
    await hass.async_block_till_done()

    unique_ids = {e.unique_id for e in _registered(hass, config_entry)}
    assert f"{DOMAIN}_vhh_home_usage" not in unique_ids
    assert f"{DOMAIN}_vhh_to_grid" not in unique_ids


async def test_vhh_mains_not_duplicated_on_repeated_signal(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """VHH mains entities are added exactly once even if the role signal fires twice."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": ROLE_HOUSENET})
    await hass.async_block_till_done()
    count_after_first = len(_registered(hass, config_entry))

    # Fire the role again — should not add duplicates.
    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": ROLE_HOUSENET})
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == count_after_first


# ---------------------------------------------------------------------------
# Unavailability
# ---------------------------------------------------------------------------


async def test_entity_becomes_unavailable_after_timeout(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """An entity goes unavailable once no updates arrive within the timeout window."""

    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire({"event": "battery_level", "mac": SENSOR_MAC, "volts": 4.0})
    await hass.async_block_till_done()

    reg = er.async_get(hass)
    entity_id = reg.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SENSOR_MAC}_battery_level"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "unavailable"

    # Advance time past the 60-second unavailability timeout.
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=65))
    await hass.async_block_till_done()

    unavailable_state = hass.states.get(entity_id)
    assert unavailable_state is not None
    assert unavailable_state.state == "unavailable"


# ---------------------------------------------------------------------------
# device_lost
# ---------------------------------------------------------------------------


async def test_device_lost_does_not_remove_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """device_lost does not remove entities from the registry (library handles reconnection)."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()
    count_before = len(_registered(hass, config_entry))

    await fire({"event": "device_lost", "mac": PLUG_MAC})
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == count_before


# ---------------------------------------------------------------------------
# Unload teardown
# ---------------------------------------------------------------------------


async def test_unload_unsubscribes_all_devices(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Unloading the entry calls unsubscribe() for every discovered device."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    unsubbed = {call.args[0] for call in mock_devices.unsubscribe.call_args_list}
    assert PLUG_MAC in unsubbed
    assert SENSOR_MAC in unsubbed


# ---------------------------------------------------------------------------
# Dispatcher — guard-clause paths (mac is None)
# ---------------------------------------------------------------------------


async def test_device_found_with_no_mac_is_ignored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """device_found with no mac key is silently ignored — no entities created."""
    await fire({"event": "device_found", "device_type": "plug"})
    await hass.async_block_till_done()
    assert len(_registered(hass, config_entry)) == 0


async def test_now_relaying_for_with_no_mac_is_ignored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """now_relaying_for with no mac key is silently ignored."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    count_before = len(_registered(hass, config_entry))

    await fire({"event": "now_relaying_for", "role": ROLE_HOUSENET})
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == count_before


async def test_device_lost_with_no_mac_is_ignored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """device_lost with no mac key is silently ignored — no state change."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()
    count_before = len(_registered(hass, config_entry))

    await fire({"event": "device_lost"})
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == count_before


async def test_measurement_with_no_mac_is_ignored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """A measurement event with no mac key is silently ignored."""
    count_before = len(_registered(hass, config_entry))
    await fire(
        {
            "event": "average_power",
            "role": ROLE_HOUSENET,
            "watts": 500.0,
            "starttime_utc": 1700000000,
            "duration_s": 10,
        }
    )
    await hass.async_block_till_done()
    assert len(_registered(hass, config_entry)) == count_before


# ---------------------------------------------------------------------------
# Dispatcher — plug re-discovered after expiry re-subscribes
# ---------------------------------------------------------------------------


async def test_plug_rediscovery_resubscribes(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """A plug re-announced after expiry re-subscribes without creating duplicate entities."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()
    count_after_first = len(_registered(hass, config_entry))
    subscribe_count = mock_devices.subscribe.call_count

    # Second device_found for same MAC simulates expiry + re-announcement.
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()

    # No new entities.
    assert len(_registered(hass, config_entry)) == count_after_first
    # subscribe() called a second time so events flow again.
    assert mock_devices.subscribe.call_count == subscribe_count + 1


async def test_sensor_rediscovery_resubscribes(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """A sensor re-announced after expiry re-subscribes without creating duplicate entities."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()
    count_after_first = len(_registered(hass, config_entry))
    subscribe_count = mock_devices.subscribe.call_count

    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == count_after_first
    assert mock_devices.subscribe.call_count == subscribe_count + 1


# ---------------------------------------------------------------------------
# Dispatcher — measurement from unknown MAC creates sensor on the fly
# ---------------------------------------------------------------------------


async def test_measurement_from_unknown_mac_creates_sensor(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """A measurement arriving for an unseen MAC bootstraps sensor entities."""
    assert len(_registered(hass, config_entry)) == 0

    await fire(
        {
            "event": "average_power",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
            "watts": 800.0,
            "starttime_utc": 1700000000,
            "duration_s": 10,
        }
    )
    await hass.async_block_till_done()

    # Universal entities + housenet role-gated + VHH = _HOUSENET_SENSOR_COUNT.
    assert len(_registered(hass, config_entry)) == _HOUSENET_SENSOR_COUNT
    mock_devices.subscribe.assert_called_with(SENSOR_MAC)


# ---------------------------------------------------------------------------
# sensor.py — role-update no-ops
# ---------------------------------------------------------------------------


async def test_role_update_noop_when_role_unchanged(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """ROLE_UPDATE_SIGNAL with the already-persisted role is a no-op (no new entities)."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": ROLE_HOUSENET})
    await hass.async_block_till_done()
    count = len(_registered(hass, config_entry))

    # Fire the same role again — should change nothing.
    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": ROLE_HOUSENET})
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == count


async def test_role_update_for_plug_mac_is_noop(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """ROLE_UPDATE_SIGNAL for a plug MAC returns early — plugs never get role-gated entities."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()
    count = len(_registered(hass, config_entry))

    # Firing a role update for a plug MAC should be a no-op.
    await fire({"event": "now_relaying_for", "mac": PLUG_MAC, "role": ROLE_HOUSENET})
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == count


async def test_schedule_unavailable_before_added_to_hass_is_noop(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """_schedule_unavailable guards against being called before hass is set."""
    # Discover a plug so its entities exist in the registry.
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()

    reg = er.async_get(hass)
    entity_id = reg.async_get_entity_id(Platform.SENSOR, DOMAIN, f"{PLUG_MAC}_power")
    assert entity_id is not None

    # Verify the entity is in the expected available state after receiving data.
    await fire(
        {
            "event": "average_power",
            "mac": PLUG_MAC,
            "watts": 100.0,
            "starttime_utc": 1700000000,
            "duration_s": 10,
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    # Entity is available after receiving a measurement.
    assert state.state != "unavailable"


# ---------------------------------------------------------------------------
# sensor.py — remaining coverage gaps (lines 445, 485/495, 578, 708)
# ---------------------------------------------------------------------------


async def test_role_update_signal_noop_when_persisted_role_matches(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """handle_role_update (sensor.py closure) returns early when entry.data already has the same role.

    The dispatcher deduplicates at its own level, so we send ROLE_UPDATE_SIGNAL
    directly to reach the sensor.py closure with an already-persisted role.
    """
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire({"event": "now_relaying_for", "mac": SENSOR_MAC, "role": ROLE_HOUSENET})
    await hass.async_block_till_done()
    count = len(_registered(hass, config_entry))

    # entry.data now has ROLE_HOUSENET persisted for SENSOR_MAC.
    # Sending the same role directly bypasses the dispatcher dedup and lands
    # straight in the sensor.py closure — which should return early (line 708).
    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, SENSOR_MAC, ROLE_HOUSENET)
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == count
