"""Test the KACO RS485 sensor platform."""

from kaco_rs485.testing import POWADOR_6400XI, CannedInverter, FakeBus
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.kaco_rs485.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

# The library calls an inverter asleep after three consecutive misses.
CYCLES_UNTIL_DARK = 4


def _entity_id(
    entity_registry: er.EntityRegistry, entry_id: str, address: int, key: str
) -> str:
    """Look an entity up by unique id rather than by a guessed slug."""
    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry_id}_{address}_{key}"
    )
    assert entity_id is not None, f"address {address} {key} was not created"
    return entity_id


async def _run_cycles(hass: HomeAssistant, entry: MockConfigEntry, count: int) -> None:
    """Drive the coordinator directly rather than through the scheduler."""
    for _ in range(count):
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test all entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_an_inverter_that_goes_dark_becomes_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_bus: FakeBus,
) -> None:
    """Test only the dark inverter goes unavailable; the rest keep reporting."""
    entry_id = init_integration.entry_id
    dark = _entity_id(entity_registry, entry_id, 1, "ac_power")
    still_lit = _entity_id(entity_registry, entry_id, 4, "ac_power")

    mock_bus.silence(1)
    await _run_cycles(hass, init_integration, CYCLES_UNTIL_DARK)

    assert hass.states.get(dark).state == STATE_UNAVAILABLE
    assert hass.states.get(still_lit).state == "681"


async def test_an_inverter_that_returns_reports_again(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_bus: FakeBus,
) -> None:
    """Test the morning after: a unit that wakes up starts reporting again."""
    entry_id = init_integration.entry_id
    ac_power = _entity_id(entity_registry, entry_id, 1, "ac_power")

    mock_bus.silence(1)
    await _run_cycles(hass, init_integration, CYCLES_UNTIL_DARK)
    assert hass.states.get(ac_power).state == STATE_UNAVAILABLE

    mock_bus.wake(1, POWADOR_6400XI)
    await _run_cycles(hass, init_integration, 2)

    assert hass.states.get(ac_power).state == "635"


async def test_a_half_answered_cycle_keeps_the_missing_half_unknown(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_bus: FakeBus,
) -> None:
    """Test command `3` going quiet keeps the last total rather than blanking it."""
    entry_id = init_integration.entry_id
    total_yield = _entity_id(entity_registry, entry_id, 1, "total_yield")
    assert hass.states.get(total_yield).state == "112706"

    # Same unit, but now silent on command `3` only.
    mock_bus.wake(
        1,
        CannedInverter(
            name="6400xi, no counters",
            replies={k: v for k, v in POWADOR_6400XI.replies.items() if k != "3"},
        ),
    )
    await _run_cycles(hass, init_integration, 1)

    assert hass.states.get(total_yield).state == "112706"
    assert (
        hass.states.get(_entity_id(entity_registry, entry_id, 1, "ac_power")).state
        == "635"
    )
