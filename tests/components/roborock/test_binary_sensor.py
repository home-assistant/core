"""Test Roborock Binary Sensor."""

import copy
from typing import Any

import pytest
from roborock.data import RoborockDockTypeCode
from roborock.device_features import RoborockDockFeatures
from roborock.exceptions import RoborockException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.roborock.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import FakeDevice

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.BINARY_SENSOR]


async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensors and check test values are correctly set."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_entry.entry_id)


def setup_coordinator_side_effect(
    fake_devices: list[FakeDevice], side_effect: Any
) -> None:
    """Set the query/refresh side effect on all fake devices to simulate failure or delay."""
    for device in fake_devices:
        if device.v1_properties is not None:
            device.v1_properties.status.refresh.side_effect = side_effect
        if device.dyad is not None:
            device.dyad.query_values.side_effect = side_effect
        if device.zeo is not None:
            device.zeo.query_values.side_effect = side_effect
        if device.b01_q10_properties is not None:
            device.b01_q10_properties.refresh.side_effect = side_effect
        if device.b01_q7_properties is not None:
            device.b01_q7_properties.query_values.side_effect = side_effect


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (RoborockException("Simulated failure"), STATE_UNAVAILABLE),
    ],
)
async def test_binary_sensors_coordinator_state(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_devices: list[FakeDevice],
    side_effect: Any,
    expected_state: str,
) -> None:
    """Test binary sensors state based on coordinator update success or delay."""
    setup_coordinator_side_effect(fake_devices, side_effect)

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    # V1 binary sensors
    state = hass.states.get("binary_sensor.roborock_s7_maxv_mop_attached")
    assert state is not None
    assert state.state == expected_state

    # A01 (Dyad/Zeo) binary sensors
    state = hass.states.get("binary_sensor.zeo_one_detergent")
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize("platforms", [[Platform.BINARY_SENSOR]])
async def test_zeo_request_protocols_filtered_by_schema(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_devices: list[FakeDevice],
) -> None:
    """Test that Zeo request protocols are filtered by the device's supported schema IDs, ensuring correct entities are created."""
    # Find the first Zeo device
    zeo_device_1 = next(
        (device for device in fake_devices if device.zeo is not None),
        None,
    )
    assert zeo_device_1 is not None

    # Create a second Zeo device without softener in its schema
    zeo_device_2 = copy.deepcopy(zeo_device_1)
    zeo_device_2.device_info.duid = "zeo_duid_2"
    zeo_device_2._duid = "zeo_duid_2"
    zeo_device_2.device_info.name = "Zeo Two"
    zeo_device_2._name = "Zeo Two"
    zeo_device_2.device_info.sn = "zeo_sn_2"

    # Exclude softener parameters: 214 (SOFTENER_TYPE) and 227 (SOFTENER_EMPTY)
    zeo_device_2.product.schema = [
        schema
        for schema in zeo_device_2.product.schema
        if schema.id not in ("214", "227")
    ]

    # Add the second device to the list of fake devices
    fake_devices.append(zeo_device_2)

    # Now set up the integration
    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    # Verify that the first Zeo device has both detergent and softener entities
    assert hass.states.get("binary_sensor.zeo_one_detergent") is not None
    assert hass.states.get("binary_sensor.zeo_one_softener") is not None

    # Verify that the second Zeo device has detergent entities but NOT softener entities
    assert hass.states.get("binary_sensor.zeo_two_detergent") is not None
    assert hass.states.get("binary_sensor.zeo_two_softener") is None


@pytest.fixture
def dock_type(request: pytest.FixtureRequest, fake_vacuum: FakeDevice) -> None:
    """Report the parametrized dock type for the fake vacuum."""
    fake_vacuum.v1_properties.device_features.dock_features = (
        RoborockDockFeatures.from_dock_type(request.param)
    )


MOP_DRYING_UNIQUE_ID = "dry_status_abc123"
MOP_DRYING_ISSUE_ID = "deprecated_mop_drying_abc123"
MOP_DRYING_ENTITY_ID = "binary_sensor.roborock_s7_maxv_dock_mop_drying"


def register_mop_drying_sensor(
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    disabled_by: er.RegistryEntryDisabler | None = None,
) -> None:
    """Register the mop drying binary sensor as an existing installation would have."""
    entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        MOP_DRYING_UNIQUE_ID,
        config_entry=config_entry,
        suggested_object_id="roborock_s7_maxv_dock_mop_drying",
        disabled_by=disabled_by,
    )


async def test_mop_drying_sensor_not_created_for_new_installs(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    setup_entry: MockConfigEntry,
) -> None:
    """Test the deprecated mop drying sensor is not created on a fresh install."""
    assert hass.states.get(MOP_DRYING_ENTITY_ID) is None
    assert (
        entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR, DOMAIN, MOP_DRYING_UNIQUE_ID
        )
        is None
    )
    assert (DOMAIN, MOP_DRYING_ISSUE_ID) not in issue_registry.issues


async def test_mop_drying_sensor_deprecated(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test an existing mop drying sensor is kept and raises a repair issue."""
    register_mop_drying_sensor(entity_registry, mock_roborock_entry)

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(MOP_DRYING_ENTITY_ID).state == "off"
    assert (DOMAIN, MOP_DRYING_ISSUE_ID) in issue_registry.issues


@pytest.mark.parametrize(
    "dock_type", [RoborockDockTypeCode.o1_dock], indirect=True, ids=["collect-only"]
)
@pytest.mark.usefixtures("dock_type")
async def test_mop_drying_sensor_removed_for_dock_without_drying(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test the sensor is removed without a repair issue when the dock cannot dry."""
    register_mop_drying_sensor(entity_registry, mock_roborock_entry)

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(MOP_DRYING_ENTITY_ID) is None
    assert (
        entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR, DOMAIN, MOP_DRYING_UNIQUE_ID
        )
        is None
    )
    assert (DOMAIN, MOP_DRYING_ISSUE_ID) not in issue_registry.issues


async def test_mop_drying_repair_cleared_when_dock_replaced(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_roborock_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test the repair issue is cleared when the dock no longer supports drying."""
    register_mop_drying_sensor(entity_registry, mock_roborock_entry)

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    assert (DOMAIN, MOP_DRYING_ISSUE_ID) in issue_registry.issues

    fake_vacuum.v1_properties.device_features.dock_features = (
        RoborockDockFeatures.from_dock_type(RoborockDockTypeCode.o1_dock)
    )
    await hass.config_entries.async_reload(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR, DOMAIN, MOP_DRYING_UNIQUE_ID
        )
        is None
    )
    assert (DOMAIN, MOP_DRYING_ISSUE_ID) not in issue_registry.issues


async def test_mop_drying_sensor_removed_when_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test a disabled mop drying sensor is removed and the repair issue cleared."""
    register_mop_drying_sensor(
        entity_registry, mock_roborock_entry, er.RegistryEntryDisabler.USER
    )

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR, DOMAIN, MOP_DRYING_UNIQUE_ID
        )
        is None
    )
    assert (DOMAIN, MOP_DRYING_ISSUE_ID) not in issue_registry.issues


async def test_mop_drying_sensor_kept_when_used_by_automation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test a mop drying sensor used by an automation is kept and the usage listed."""
    register_mop_drying_sensor(
        entity_registry, mock_roborock_entry, er.RegistryEntryDisabler.USER
    )
    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: {
                "alias": "test_automation",
                "triggers": {
                    "trigger": "state",
                    "entity_id": MOP_DRYING_ENTITY_ID,
                },
                "actions": {"action": "notify.notify", "data": {}},
            }
        },
    )

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR, DOMAIN, MOP_DRYING_UNIQUE_ID
        )
        is not None
    )
    issue = issue_registry.async_get_issue(DOMAIN, MOP_DRYING_ISSUE_ID)
    assert issue.translation_key == "deprecated_mop_drying_scripts"
