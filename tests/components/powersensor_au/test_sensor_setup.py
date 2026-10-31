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
from unittest.mock import AsyncMock, MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.powersensor_au.config_flow import PowersensorConfigFlow
from homeassistant.components.powersensor_au.const import (
    CFG_ROLES,
    DOMAIN,
    ROLE_APPLIANCE,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_WATER,
)
from homeassistant.const import EVENT_STATE_REPORTED, Platform
from homeassistant.core import Event, EventStateReportedData, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utc_from_timestamp, utcnow

PLUG_MAC = "aabbccddeeff"
SENSOR_MAC = "112233445566"
SOLAR_MAC = "665544332211"
# A role newer firmware might report that this integration does not know.
UNRECOGNISED_ROLE = "gas"

PLUG_ENTITIES = {
    f"{PLUG_MAC}_{key}"
    for key in (
        "power",
        "volts",
        "apparent_current",
        "active_current",
        "reactive_current",
        "total_energy",
        "device_role",
    )
}
# The entities a sensor's role adds to those every sensor has.
ENERGY_KEYS = ("power", "total_energy")
WATER_KEYS = ("water_flow_rate", "total_water_consumption")
HOUSEHOLD_MAINS_ENTITIES = {
    "vhh_home_usage",
    "vhh_from_grid",
    "vhh_home_usage_summation",
    "vhh_from_grid_summation",
}
HOUSEHOLD_SOLAR_ENTITIES = {
    "vhh_to_grid",
    "vhh_solar_generation",
    "vhh_to_grid_summation",
    "vhh_solar_generation_summation",
}


def _sensor_entities(mac: str, *role_keys: str) -> set[str]:
    """Return the unique IDs of a sensor's entities, given its role's keys."""
    return {
        f"{mac}_{key}"
        for key in ("battery_level", "device_role", "rssi_ble", *role_keys)
    }


MAINS_SENSOR_ENTITIES = _sensor_entities(SENSOR_MAC, *ENERGY_KEYS)


def _unique_ids(entity_registry: er.EntityRegistry, entry: MockConfigEntry) -> set[str]:
    """Return the unique IDs of the entry's entities."""
    return {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }


async def test_plug_discovery_creates_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
) -> None:
    """A device_found plug event creates all PLUG_DESCRIPTIONS entities."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()

    assert _unique_ids(entity_registry, config_entry) == PLUG_ENTITIES


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

    assert _unique_ids(entity_registry, entry) == (
        PLUG_ENTITIES | MAINS_SENSOR_ENTITIES | HOUSEHOLD_MAINS_ENTITIES
    )
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
    entity_registry: er.EntityRegistry,
) -> None:
    """A sensor with role=None only gets the three universal entities."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    assert _unique_ids(entity_registry, config_entry) == _sensor_entities(SENSOR_MAC)


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_sensor_with_persisted_housenet_role_creates_full_entities(
    hass: HomeAssistant,
    mock_devices: MagicMock,
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

    assert _unique_ids(entity_registry, entry) == (
        MAINS_SENSOR_ENTITIES | HOUSEHOLD_MAINS_ENTITIES
    )


async def test_now_relaying_for_triggers_role_update(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
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

    assert _unique_ids(entity_registry, config_entry) == (
        MAINS_SENSOR_ENTITIES | HOUSEHOLD_MAINS_ENTITIES
    )


async def test_now_relaying_for_without_role_is_a_noop(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
) -> None:
    """now_relaying_for with no/unknown role does not create role-gated entities."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    await fire(
        {
            "event": "now_relaying_for",
            "device_type": "sensor",
            "mac": SENSOR_MAC,
            "role": "unknown",
        }
    )
    await hass.async_block_till_done()

    assert _unique_ids(entity_registry, config_entry) == _sensor_entities(SENSOR_MAC)


async def test_measurement_with_role_creates_role_gated_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
) -> None:
    """An average_power measurement carrying a role triggers entity creation."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    assert _unique_ids(entity_registry, config_entry) == _sensor_entities(SENSOR_MAC)

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

    assert _unique_ids(entity_registry, config_entry) == (
        MAINS_SENSOR_ENTITIES | HOUSEHOLD_MAINS_ENTITIES
    )


@pytest.mark.usefixtures("config_entry")
async def test_measurement_updates_entity_state(
    hass: HomeAssistant,
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


@pytest.mark.usefixtures("config_entry")
async def test_battery_level_converted_from_volts(
    hass: HomeAssistant,
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


@pytest.mark.usefixtures("config_entry")
async def test_energy_converted_from_joules(
    hass: HomeAssistant,
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
@pytest.mark.usefixtures("config_entry")
async def test_energy_last_reset_follows_device_reset(
    hass: HomeAssistant,
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
    entity_registry: er.EntityRegistry,
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

    assert _unique_ids(entity_registry, config_entry) == _sensor_entities(
        SENSOR_MAC, *WATER_KEYS
    )


async def test_role_change_adds_entities_without_duplicates(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
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
    housenet_entities = MAINS_SENSOR_ENTITIES | HOUSEHOLD_MAINS_ENTITIES
    assert _unique_ids(entity_registry, config_entry) == housenet_entities

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
    after_water_entities = housenet_entities | _sensor_entities(SENSOR_MAC, *WATER_KEYS)
    assert _unique_ids(entity_registry, config_entry) == after_water_entities

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
    assert _unique_ids(entity_registry, config_entry) == after_water_entities


async def test_vhh_mains_entities_created_when_housenet_sensor_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
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

    unique_ids = _unique_ids(entity_registry, config_entry)
    assert unique_ids >= HOUSEHOLD_MAINS_ENTITIES
    assert not HOUSEHOLD_SOLAR_ENTITIES & unique_ids


async def test_vhh_solar_entities_added_when_solar_sensor_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
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

    assert _unique_ids(entity_registry, config_entry) >= HOUSEHOLD_SOLAR_ENTITIES


async def test_vhh_solar_not_created_without_mains(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
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

    assert _unique_ids(entity_registry, config_entry) == _sensor_entities(
        SOLAR_MAC, *ENERGY_KEYS
    )


async def test_repeated_role_adds_no_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
) -> None:
    """A sensor reporting the role it already has adds no entities, household view included."""
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
    assert _unique_ids(entity_registry, config_entry) == (
        MAINS_SENSOR_ENTITIES | HOUSEHOLD_MAINS_ENTITIES
    )

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

    assert _unique_ids(entity_registry, config_entry) == (
        MAINS_SENSOR_ENTITIES | HOUSEHOLD_MAINS_ENTITIES
    )


@pytest.mark.usefixtures("config_entry")
async def test_unchanged_role_keeps_device_role_available_without_writes(
    hass: HomeAssistant,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A repeated role keeps device_role available without writing its state.

    The role comes with every measurement only to keep device_role available.
    Measurements themselves are still written each time, even when unchanged.
    """
    reading = {
        "event": "average_power",
        "mac": PLUG_MAC,
        "role": ROLE_APPLIANCE,
        "watts": 50.0,
        "starttime_utc": 1700000000,
        "duration_s": 1,
    }
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await fire(reading)
    await hass.async_block_till_done()
    role_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{PLUG_MAC}_device_role"
    )
    power_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{PLUG_MAC}_power"
    )
    assert role_id is not None
    assert power_id is not None

    reported: list[str] = []

    @callback
    def _ours(event_data: EventStateReportedData) -> bool:
        return event_data["entity_id"] in (role_id, power_id)

    @callback
    def _record(event: Event[EventStateReportedData]) -> None:
        reported.append(event.data["entity_id"])

    hass.bus.async_listen(EVENT_STATE_REPORTED, _record, event_filter=_ours)

    # Readings keep arriving well past the plug's 60 s timeout.
    for _ in range(3):
        freezer.tick(timedelta(seconds=50))
        await fire(reading)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    role_state = hass.states.get(role_id)
    assert role_state is not None
    assert role_state.state == "appliance"
    assert reported.count(role_id) == 0
    assert reported.count(power_id) == 3

    # Once unavailable, the same role is written again when readings resume.
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    role_state = hass.states.get(role_id)
    assert role_state is not None
    assert role_state.state == "unavailable"

    await fire(reading)
    await hass.async_block_till_done()
    role_state = hass.states.get(role_id)
    assert role_state is not None
    assert role_state.state == "appliance"


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
@pytest.mark.usefixtures("config_entry")
async def test_entity_becomes_unavailable_after_timeout(
    hass: HomeAssistant,
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
    entity_registry: er.EntityRegistry,
) -> None:
    """device_lost does not remove entities from the registry (library handles reconnection)."""
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()

    await fire({"event": "device_lost", "mac": PLUG_MAC})
    await hass.async_block_till_done()

    assert _unique_ids(entity_registry, config_entry) == PLUG_ENTITIES


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(
            {"event": "device_found", "device_type": "plug"}, id="device_found"
        ),
        pytest.param(
            {
                "event": "now_relaying_for",
                "device_type": "sensor",
                "role": ROLE_HOUSENET,
            },
            id="now_relaying_for",
        ),
        pytest.param({"event": "device_lost"}, id="device_lost"),
        pytest.param(
            {
                "event": "average_power",
                "role": ROLE_HOUSENET,
                "watts": 500.0,
                "starttime_utc": 1700000000,
                "duration_s": 10,
            },
            id="measurement",
        ),
    ],
)
async def test_event_with_no_mac_is_ignored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
    event: dict[str, Any],
) -> None:
    """An event with no mac key adds or removes no entities, and saves no role."""
    await fire({"event": "device_found", "mac": SENSOR_MAC, "device_type": "sensor"})
    await hass.async_block_till_done()

    await fire(event)
    await hass.async_block_till_done()

    assert _unique_ids(entity_registry, config_entry) == _sensor_entities(SENSOR_MAC)
    assert config_entry.data[CFG_ROLES] == {}


@pytest.mark.parametrize(
    ("mac", "device_type", "entities"),
    [
        pytest.param(PLUG_MAC, "plug", PLUG_ENTITIES, id="plug"),
        pytest.param(SENSOR_MAC, "sensor", _sensor_entities(SENSOR_MAC), id="sensor"),
    ],
)
async def test_rediscovery_resubscribes_without_duplicates(
    hass: HomeAssistant,
    mock_devices: MagicMock,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
    mac: str,
    device_type: str,
    entities: set[str],
) -> None:
    """A device announced again after expiry is subscribed again, and gets no new entities.

    The library drops a device's subscription when it expires, so its events
    only flow again if it is subscribed again when it returns.
    """
    await fire({"event": "device_found", "mac": mac, "device_type": device_type})
    await hass.async_block_till_done()
    await fire({"event": "device_found", "mac": mac, "device_type": device_type})
    await hass.async_block_till_done()

    assert _unique_ids(entity_registry, config_entry) == entities
    assert mock_devices.subscribe.call_args_list == [call(mac), call(mac)]


async def test_now_relaying_for_other_than_a_sensor_is_ignored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    entity_registry: er.EntityRegistry,
) -> None:
    """A now_relaying_for for anything but a sensor is ignored.

    A plug can't relay another plug, so the library only creates this event for
    sensors.  This guards against anything else being treated as a sensor.
    """
    await fire({"event": "device_found", "mac": PLUG_MAC, "device_type": "plug"})
    await hass.async_block_till_done()

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
    assert _unique_ids(entity_registry, config_entry) == PLUG_ENTITIES
    assert PLUG_MAC not in config_entry.data[CFG_ROLES]
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_sensors_found"


async def test_role_change_writes_device_registry_once(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fire: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
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
    assert _unique_ids(entity_registry, config_entry) == (
        MAINS_SENSOR_ENTITIES | HOUSEHOLD_MAINS_ENTITIES
    )

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
