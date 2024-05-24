"""Test the sensor classes."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.zeversolar.sensor import ZeversolarEntityDescription
from homeassistant.const import EntityCategory, Platform, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import snapshot_platform


async def ZeversolarEntityDescription_constructor(hass: HomeAssistant) -> None:
    """Perform simple tests for construction and initialization."""

    description = ZeversolarEntityDescription(
        key="pac",
        translation_key="pac",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda data: data.pac,
    )

    assert type(description) is ZeversolarEntityDescription
    assert issubclass(type(description), SensorEntityDescription)


async def test_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test sensors."""

    with patch(
        "homeassistant.components.zeversolar.PLATFORMS",
        [Platform.SENSOR],
    ):
        entry = await init_integration(hass)

        await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
