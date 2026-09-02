"""Test the Ecowitt WS90 sensor platform."""

from ecowitt_ws90_modbus import WS90
from modbus_connection.mock import MockModbusConnection
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ecowitt_ws90.const import DOMAIN
from homeassistant.components.ecowitt_ws90.sensor import SENSOR_DESCRIPTIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform


def test_sensor_descriptions_read_real_fields() -> None:
    """Guard SENSOR_DESCRIPTIONS against a component transcription slip.

    Values are resolved by getattr, so a wrong component name would other-
    wise show up as a permanently empty sensor rather than an error.
    """
    device = WS90(MockModbusConnection().for_unit(1))
    for description in SENSOR_DESCRIPTIONS:
        assert hasattr(device, description.component), (
            f"unknown component {description.component!r}"
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test all ten sensors, enabled or not, match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_rain_counter_disabled_by_default(
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the finer-resolution rain counter is disabled by default."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_rain_counter"
    )
    assert entity_id is not None

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
