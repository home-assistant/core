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
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.powersensor_au.config_flow import PowersensorConfigFlow
from homeassistant.components.powersensor_au.const import (
    CFG_ROLES,
    DOMAIN,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_WATER,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utc_from_timestamp, utcnow

PLUG_MAC = "aabbccddeeff"
SENSOR_MAC = "112233445566"
SOLAR_MAC = "665544332211"
# A role newer firmware might report that this integration does not know.
UNRECOGNISED_ROLE = "gas"

# Expected entity counts from sensor.py description tuples.
_UNIVERSAL_SENSOR_COUNT = 3  # battery_level, device_role, rssi_ble
# 3 universal + 2 role-gated (power, total_energy) + 4 VHH consumption entities
_HOUSENET_SENSOR_COUNT = 9
# 3 universal + 2 role-gated (water_flow_rate, total_water_consumption)
_WATER_SENSOR_COUNT = 5
_PLUG_COUNT = 7  # all PLUG_DESCRIPTIONS
_CONSUMPTION_VHH_COUNT = 4  # CONSUMPTION_DESCRIPTIONS
_PRODUCTION_VHH_COUNT = 4  # PRODUCTION_DESCRIPTIONS


def _registered(hass: HomeAssistant, entry: MockConfigEntry) -> list[er.RegistryEntry]:
    reg = er.async_get(hass)
    return er.async_entries_for_config_entry(reg, entry.entry_id)


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


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_devices_found_before_platform_setup_are_seeded(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Devices discovered before the sensor platform loads get entities and roles.

    Discovery starts before platforms are forwarded, so CREATE and ROLE_UPDATE
    signals fired in that window have no listener.  Delivering the events from
    inside start() reproduces that window exactly.  A role learned in it must
    still be saved, as measurements without a role fall back to the saved one.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"roles": {}},
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )
    entry.add_to_hass(hass)

    async def _start_and_discover(
        cb: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        await cb({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
        await cb({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
        await cb(
            {
                "event": "now_relaying_for",
                "device_type": "sensor",
                "mac": SENSOR_MAC,
                "role": ROLE_HOUSENET,
            }
        )

    mock_devices.start = AsyncMock(side_effect=_start_and_discover)

    with patch(
        "homeassistant.components.powersensor_au.PowersensorZeroconfDevices",
        return_value=mock_devices,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == _PLUG_COUNT + _HOUSENET_SENSOR_COUNT

    unique_ids = {e.unique_id for e in entities}
    assert f"{PLUG_MAC}_power" in unique_ids
    assert f"{SENSOR_MAC}_power" in unique_ids
    assert f"{SENSOR_MAC}_total_energy" in unique_ids
    assert "vhh_home_usage" in unique_ids
    assert entry.data[CFG_ROLES] == {SENSOR_MAC: ROLE_HOUSENET}

    fire = mock_devices.start.call_args[0][0]
    await fire(
        {
            "event": "average_power",
            "mac": SENSOR_MAC,
            "watts": 500.0,
            "starttime_utc": 1700000000,
            "duration_s": 30,
        }
    )
    await hass.async_block_till_done()
    role_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SENSOR_MAC}_device_role"
    )
    assert role_entity_id is not None
    role_state = hass.states.get(role_entity_id)
    assert role_state is not None
    assert role_state.state == "house_net"
    # The household view counts the sensor's power.
    home_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "vhh_home_usage"
    )
    assert home_entity_id is not None
    home_state = hass.states.get(home_entity_id)
    assert home_state is not None
    assert home_state.state == "500"


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


async def test_sensor_with_persisted_housenet_role_creates_full_entities(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    mock_async_zeroconf: MagicMock,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
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

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == _HOUSENET_SENSOR_COUNT

    unique_ids = {e.unique_id for e in entities}
    assert f"{SENSOR_MAC}_power" in unique_ids
    assert f"{SENSOR_MAC}_total_energy" in unique_ids


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
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
        }
    )
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

    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": "unknown",
        }
    )
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == count_before


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
    entity_registry: er.EntityRegistry,
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

    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SENSOR_MAC}_power"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(850.5, rel=1e-3)


async def test_battery_level_converted_from_volts(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
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

    entity_id = entity_registry.async_get_entity_id(
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
    entity_registry: er.EntityRegistry,
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
            "starttime_utc": 1700000000,
            "summation_resettime_utc": 1690000000,
        }
    )
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SENSOR_MAC}_total_energy"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(1.0, rel=1e-4)


@pytest.mark.parametrize(
    ("discovery", "mac"),
    [
        pytest.param(
            [
                {"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"},
                {
                    "event": "now_relaying_for",
                    "device_type": "sensor",
                    "mac": SENSOR_MAC,
                    "role": ROLE_HOUSENET,
                },
            ],
            SENSOR_MAC,
            id="sensor",
        ),
        pytest.param(
            [{"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"}],
            PLUG_MAC,
            id="plug",
        ),
    ],
)
async def test_energy_last_reset_follows_device_reset(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
    discovery: list[dict[str, Any]],
    mac: str,
) -> None:
    """The energy total's last_reset follows the device's counter resets.

    Without it, the drop to zero at a reset would be recorded in statistics as
    negative energy, because the entity's state class is TOTAL.
    """
    for event in discovery:
        await fire(event)
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{mac}_total_energy"
    )
    assert entity_id is not None

    await fire(
        {
            "event": "summation_energy",
            "mac": mac,
            "summation_joules": 18_000_000,  # 5 kWh
            "starttime_utc": 1700000000,
            "summation_resettime_utc": 1690000000,
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "5.0"
    assert state.attributes["last_reset"] == utc_from_timestamp(1690000000).isoformat()

    # The device resets its counter to zero.
    await fire(
        {
            "event": "summation_energy",
            "mac": mac,
            "summation_joules": 0,
            "starttime_utc": 1700000030,
            "summation_resettime_utc": 1700000020,
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0.0"
    assert state.attributes["last_reset"] == utc_from_timestamp(1700000020).isoformat()


async def test_water_sensor_creates_water_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """A sensor assigned ROLE_WATER gets flow-rate and volume entities."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_WATER,
        }
    )
    await hass.async_block_till_done()

    entities = _registered(hass, config_entry)
    assert len(entities) == _WATER_SENSOR_COUNT

    unique_ids = {e.unique_id for e in entities}
    assert f"{SENSOR_MAC}_water_flow_rate" in unique_ids
    assert f"{SENSOR_MAC}_total_water_consumption" in unique_ids


async def test_role_change_adds_entities_without_duplicates(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Changing role from house-net to water adds water entities; going back is a noop."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
        }
    )
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


async def test_vhh_mains_entities_created_when_housenet_sensor_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Mains VHH entities are added once a house-net sensor is discovered."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
        }
    )
    await hass.async_block_till_done()

    unique_ids = {e.unique_id for e in _registered(hass, config_entry)}
    assert "vhh_home_usage" in unique_ids
    assert "vhh_from_grid" in unique_ids
    assert "vhh_home_usage_summation" in unique_ids
    assert "vhh_from_grid_summation" in unique_ids


async def test_vhh_solar_entities_added_when_solar_sensor_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Solar VHH entities are added when a solar sensor joins alongside a mains sensor."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
        }
    )
    await fire({"event": "device_found", "mac": SOLAR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SOLAR_MAC,
            "role": ROLE_SOLAR,
        }
    )
    await hass.async_block_till_done()

    unique_ids = {e.unique_id for e in _registered(hass, config_entry)}
    assert "vhh_to_grid" in unique_ids
    assert "vhh_solar_generation" in unique_ids


async def test_vhh_solar_not_created_without_mains(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Solar VHH entities are NOT created when there is no mains sensor."""
    await fire({"event": "device_found", "mac": SOLAR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SOLAR_MAC,
            "role": ROLE_SOLAR,
        }
    )
    await hass.async_block_till_done()

    unique_ids = {e.unique_id for e in _registered(hass, config_entry)}
    assert "vhh_home_usage" not in unique_ids
    assert "vhh_to_grid" not in unique_ids


async def test_vhh_mains_not_duplicated_on_repeated_signal(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """VHH mains entities are added exactly once even if the role signal fires twice."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
        }
    )
    await hass.async_block_till_done()
    count_after_first = len(_registered(hass, config_entry))

    # Fire the role again — should not add duplicates.
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
        }
    )
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == count_after_first


@pytest.mark.parametrize(
    ("mac", "device_type", "message", "key", "timeout"),
    [
        pytest.param(
            SENSOR_MAC,
            "sensor",
            {"event": "battery_level", "volts": 4.0},
            "battery_level",
            300,
            id="sensor",
        ),
        pytest.param(
            PLUG_MAC,
            "plug",
            {
                "event": "average_power",
                "watts": 100.0,
                "starttime_utc": 1700000000,
                "duration_s": 1,
            },
            "power",
            60,
            id="plug",
        ),
    ],
)
async def test_entity_becomes_unavailable_after_timeout(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
    mac: str,
    device_type: str,
    message: dict[str, Any],
    key: str,
    timeout: int,
) -> None:
    """An entity goes unavailable once no updates arrive within its device's timeout."""

    await fire({"event": "device_found", "mac": mac, "device_type": device_type})
    await fire({**message, "mac": mac})
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{mac}_{key}"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "unavailable"

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=timeout - 5))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "unavailable"

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=timeout + 5))
    await hass.async_block_till_done()

    unavailable_state = hass.states.get(entity_id)
    assert unavailable_state is not None
    assert unavailable_state.state == "unavailable"


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

    await fire(
        {"event": "now_relaying_for", "device_type": "sensor", "role": ROLE_HOUSENET}
    )
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


async def test_role_update_noop_when_role_unchanged(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """A sensor reporting the role it already has gets no new entities."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
        }
    )
    await hass.async_block_till_done()
    count = len(_registered(hass, config_entry))

    # Fire the same role again — should change nothing.
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
        }
    )
    await hass.async_block_till_done()

    assert len(_registered(hass, config_entry)) == count


async def test_now_relaying_for_other_than_a_sensor_is_ignored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """A now_relaying_for for anything but a sensor is ignored.

    A plug can't relay another plug, so the library only creates this event for
    sensors.  This guards against anything else being treated as a sensor.
    """
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()
    count = len(_registered(hass, config_entry))

    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "plug",
            "mac": PLUG_MAC,
            "role": ROLE_HOUSENET,
        }
    )
    await hass.async_block_till_done()

    # Not counted as a mains sensor, so no household view entities either.
    assert len(_registered(hass, config_entry)) == count
    assert PLUG_MAC not in config_entry.data[CFG_ROLES]
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_sensors_found"


async def test_role_change_writes_device_registry_once(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    device_registry: dr.DeviceRegistry,
) -> None:
    """A role change renames the device with a single registry write.

    The device is named after its role, and every entity of the sensor sees the
    role change, so the rename must not be done once per entity.
    """
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
        }
    )
    await hass.async_block_till_done()
    assert len(_registered(hass, config_entry)) > 1

    # house-net and solar gate the same entities, so nothing is added here and
    # every write seen comes from the rename itself.
    with patch.object(
        device_registry,
        "async_get_or_create",
        wraps=device_registry.async_get_or_create,
    ) as mock_get_or_create:
        await fire(
            {
                "event": "now_relaying_for",
                "device_type": "sensor",
                "mac": SENSOR_MAC,
                "role": ROLE_SOLAR,
            }
        )
        await hass.async_block_till_done()

    assert mock_get_or_create.call_count == 1

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SENSOR_MAC), config_entry.entry_id
    )
    assert device is not None
    assert device.name == f"Solar sensor ({SENSOR_MAC})"


async def test_unrecognised_role_is_shown_as_unknown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A role outside the ENUM options is displayed as unknown rather than rejected.

    Only the display is clamped; the reported role is still persisted.
    """
    caplog.set_level(logging.DEBUG)
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await fire(
        {
            "event": "battery_level",
            "mac": SENSOR_MAC,
            "role": ROLE_HOUSENET,
            "volts": 4.0,
        }
    )
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SENSOR_MAC}_device_role"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "house_net"

    for _ in range(3):
        await fire(
            {
                "event": "battery_level",
                "mac": SENSOR_MAC,
                "role": UNRECOGNISED_ROLE,
                "volts": 4.0,
            }
        )
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unknown"
    assert "not in the list of options" not in caplog.text
    assert caplog.text.count(f"Unrecognised role '{UNRECOGNISED_ROLE}'") == 1
    assert config_entry.data["roles"][SENSOR_MAC] == UNRECOGNISED_ROLE

    await fire(
        {"event": "battery_level", "mac": SENSOR_MAC, "role": ROLE_SOLAR, "volts": 4.0}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "solar"
