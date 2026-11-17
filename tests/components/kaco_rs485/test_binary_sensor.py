"""Test the KACO RS485 binary sensor platform."""

from freezegun.api import FrozenDateTimeFactory
from kaco_rs485.protocol import kaco_sum_checksum
from kaco_rs485.testing import POWADOR_6400XI, CannedInverter, FakeBus
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.kaco_rs485.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import CYCLES_UNTIL_DARK, run_cycles


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the binary sensor platform."""
    return [Platform.BINARY_SENSOR]


@pytest.fixture
def tripped_inverter() -> CannedInverter:
    """A 6400xi reporting status 14, grid failure."""
    raw = bytearray(POWADOR_6400XI.replies["0"])
    assert raw[5:9] == b"   4"
    raw[5:9] = b"  14"
    raw[57] = kaco_sum_checksum(bytes(raw[1:57]))
    return CannedInverter(
        name="6400xi, grid failure",
        replies={**POWADOR_6400XI.replies, "0": bytes(raw)},
    )


@pytest.fixture
def fault_entity_id(
    entity_registry: er.EntityRegistry, init_integration: MockConfigEntry
) -> str:
    """The fault sensor of the inverter at address 1."""
    entity_id = entity_registry.async_get_entity_id(
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{init_integration.entry_id}_1_fault"
    )
    assert entity_id is not None
    return entity_id


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test all entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_a_tripped_inverter_reports_a_fault(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_bus: FakeBus,
    tripped_inverter: CannedInverter,
    fault_entity_id: str,
) -> None:
    """Test a fault status code turns the sensor on."""
    mock_bus.wake(1, tripped_inverter)
    await run_cycles(hass, freezer, 1)

    assert hass.states.get(fault_entity_id).state == STATE_ON


async def test_a_recovered_inverter_clears_the_fault(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_bus: FakeBus,
    tripped_inverter: CannedInverter,
    fault_entity_id: str,
) -> None:
    """Test the sensor turns off again once the inverter leaves the fault state."""
    mock_bus.wake(1, tripped_inverter)
    await run_cycles(hass, freezer, 1)
    assert hass.states.get(fault_entity_id).state == STATE_ON

    mock_bus.wake(1, POWADOR_6400XI)
    await run_cycles(hass, freezer, 1)

    assert hass.states.get(fault_entity_id).state == STATE_OFF


async def test_a_dark_inverter_is_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_bus: FakeBus,
    fault_entity_id: str,
) -> None:
    """Test a silent inverter does not keep reporting its last fault state."""
    mock_bus.silence(1)
    await run_cycles(hass, freezer, CYCLES_UNTIL_DARK)

    assert hass.states.get(fault_entity_id).state == STATE_UNAVAILABLE
