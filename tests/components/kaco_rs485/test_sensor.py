"""Test the KACO RS485 sensor platform."""

from freezegun.api import FrozenDateTimeFactory
from kaco_rs485 import BusError
from kaco_rs485.testing import POWADOR_6400XI, CannedInverter, FakeBus
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.kaco_rs485.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import CYCLES_UNTIL_DARK, run_cycles


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the sensor platform."""
    return [Platform.SENSOR]


def _entity_id(
    entity_registry: er.EntityRegistry, entry_id: str, address: int, key: str
) -> str:
    """Look an entity up by unique id rather than by a guessed slug."""
    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry_id}_{address}_{key}"
    )
    assert entity_id is not None, f"address {address} {key} was not created"
    return entity_id


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
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
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_bus: FakeBus,
) -> None:
    """Test only the dark inverter goes unavailable; the rest keep reporting."""
    entry_id = init_integration.entry_id
    dark = _entity_id(entity_registry, entry_id, 1, "ac_power")
    still_lit = _entity_id(entity_registry, entry_id, 4, "ac_power")

    mock_bus.silence(1)
    await run_cycles(hass, freezer, CYCLES_UNTIL_DARK)

    assert hass.states.get(dark).state == STATE_UNAVAILABLE
    assert hass.states.get(still_lit).state == "681"


async def test_an_inverter_that_returns_reports_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_bus: FakeBus,
) -> None:
    """Test the morning after: a unit that wakes up starts reporting again."""
    entry_id = init_integration.entry_id
    ac_power = _entity_id(entity_registry, entry_id, 1, "ac_power")

    mock_bus.silence(1)
    await run_cycles(hass, freezer, CYCLES_UNTIL_DARK)
    assert hass.states.get(ac_power).state == STATE_UNAVAILABLE

    mock_bus.wake(1, POWADOR_6400XI)
    await run_cycles(hass, freezer, 2)

    assert hass.states.get(ac_power).state == "635"


async def test_a_half_answered_cycle_keeps_the_last_counters(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_bus: FakeBus,
) -> None:
    """Test command `3` going quiet keeps the last total rather than blanking it."""
    entry_id = init_integration.entry_id
    total_yield = _entity_id(entity_registry, entry_id, 1, "total_yield")
    daily_peak_power = _entity_id(entity_registry, entry_id, 1, "daily_peak_power")
    assert hass.states.get(total_yield).state == "112706"
    assert hass.states.get(daily_peak_power).state == "4899"

    # Same unit, but now silent on command `3` only.
    mock_bus.wake(
        1,
        CannedInverter(
            name="6400xi, no counters",
            replies={k: v for k, v in POWADOR_6400XI.replies.items() if k != "3"},
        ),
    )
    await run_cycles(hass, freezer, 1)

    assert hass.states.get(total_yield).state == "112706"
    assert hass.states.get(daily_peak_power).state == "4899"
    assert (
        hass.states.get(_entity_id(entity_registry, entry_id, 1, "ac_power")).state
        == "635"
    )


async def test_a_lost_bus_is_reopened(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_bus: FakeBus,
) -> None:
    """Test a bus lost after setup is closed, retried, and recovers."""
    ac_power = _entity_id(entity_registry, init_integration.entry_id, 1, "ac_power")

    mock_bus.request_error = BusError("connection closed")
    await run_cycles(hass, freezer, 1)
    assert hass.states.get(ac_power).state == STATE_UNAVAILABLE
    assert not mock_bus.opened

    mock_bus.open_error = BusError("could not open /dev/ttyUSB0")
    await run_cycles(hass, freezer, 1)
    assert hass.states.get(ac_power).state == STATE_UNAVAILABLE

    mock_bus.request_error = None
    mock_bus.open_error = None
    await run_cycles(hass, freezer, 1)
    assert mock_bus.opened
    assert hass.states.get(ac_power).state == "635"
