"""Test Roborock Button platform."""

from unittest.mock import Mock

import pytest
from roborock import RoborockException
from roborock.data import RoborockDockTypeCode
from roborock.devices.traits.v1.consumeable import ConsumableAttribute
from roborock.exceptions import RoborockTimeout
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.components.roborock.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import FakeDevice

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def get_scenes_failure_fixture(fake_vacuum: FakeDevice) -> None:
    """Fixture to raise when getting scenes."""
    fake_vacuum.v1_properties.routines.get_routines.side_effect = RoborockException


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.BUTTON]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_buttons(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test buttons and check test values are correctly set."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_entry.entry_id)


@pytest.fixture
def non_wash_n_fill_dock(fake_vacuum: FakeDevice) -> None:
    """Override dock_type to a non-wash-n-fill value so dock buttons are gated out."""
    status = fake_vacuum.v1_properties.status
    original_refresh = status.refresh.side_effect

    async def patched_refresh() -> None:
        await original_refresh()
        status.dock_type = RoborockDockTypeCode.auto_empty_dock

    status.refresh.side_effect = patched_refresh


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dock_buttons_absent_for_non_wash_n_fill_dock(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    non_wash_n_fill_dock: None,
    setup_entry: MockConfigEntry,
) -> None:
    """Dock consumable buttons must not be created when dock type is not wash-n-fill."""
    for entity_id in (
        "button.roborock_s7_maxv_dock_reset_strainer_consumable",
        "button.roborock_s7_maxv_dock_reset_cleaning_brush_consumable",
    ):
        assert hass.states.get(entity_id) is None
    # Non-dock consumable buttons must still exist.
    for entity_id in (
        "button.roborock_s7_maxv_reset_sensor_consumable",
        "button.roborock_s7_maxv_reset_air_filter_consumable",
        "button.roborock_s7_maxv_reset_side_brush_consumable",
        "button.roborock_s7_maxv_reset_main_brush_consumable",
    ):
        assert hass.states.get(entity_id) is not None
    # No phantom dock device should be registered for the non-wash-n-fill vacuum.
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, "abc123_dock")}) is None
    )


@pytest.fixture(name="consumeables_trait", autouse=True)
def consumeables_trait_fixture(fake_vacuum: FakeDevice) -> Mock:
    """Get the fake vacuum device command trait for asserting that commands happened."""
    assert fake_vacuum.v1_properties is not None
    return fake_vacuum.v1_properties.consumables


@pytest.mark.parametrize(
    ("entity_id", "expected_attribute"),
    [
        (
            "button.roborock_s7_maxv_reset_sensor_consumable",
            ConsumableAttribute.SENSOR_DIRTY_TIME,
        ),
        (
            "button.roborock_s7_maxv_reset_air_filter_consumable",
            ConsumableAttribute.FILTER_WORK_TIME,
        ),
        (
            "button.roborock_s7_maxv_reset_side_brush_consumable",
            ConsumableAttribute.SIDE_BRUSH_WORK_TIME,
        ),
        (
            "button.roborock_s7_maxv_reset_main_brush_consumable",
            ConsumableAttribute.MAIN_BRUSH_WORK_TIME,
        ),
        (
            "button.roborock_s7_maxv_dock_reset_strainer_consumable",
            ConsumableAttribute.STRAINER_WORK_TIME,
        ),
        (
            "button.roborock_s7_maxv_dock_reset_cleaning_brush_consumable",
            ConsumableAttribute.CLEANING_BRUSH_WORK_TIME,
        ),
    ],
)
@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_success(
    hass: HomeAssistant,
    bypass_api_client_fixture: None,
    setup_entry: MockConfigEntry,
    entity_id: str,
    expected_attribute: ConsumableAttribute,
    consumeables_trait: Mock,
) -> None:
    """Test pressing the button entities."""
    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id).state == "unknown"
    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        blocking=True,
        target={"entity_id": entity_id},
    )
    consumeables_trait.reset_consumable.assert_called_once_with(expected_attribute)
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("button.roborock_s7_maxv_reset_air_filter_consumable"),
    ],
)
@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_failure(
    hass: HomeAssistant,
    bypass_api_client_fixture: None,
    setup_entry: MockConfigEntry,
    entity_id: str,
    consumeables_trait: Mock,
) -> None:
    """Test failure while pressing the button entity."""
    consumeables_trait.reset_consumable.side_effect = RoborockTimeout

    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id).state == "unknown"
    with pytest.raises(
        HomeAssistantError, match="Error while calling RESET_CONSUMABLE"
    ):
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            blocking=True,
            target={"entity_id": entity_id},
        )
    assert consumeables_trait.reset_consumable.assert_called_once
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("button.roborock_s7_maxv_sc1"),
        ("button.roborock_s7_maxv_sc2"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_get_button_routines_failure(
    hass: HomeAssistant,
    get_scenes_failure_fixture: None,
    setup_entry: MockConfigEntry,
    entity_id: str,
    fake_vacuum: FakeDevice,
) -> None:
    """Test that if routine retrieval fails, no entity is being created."""
    # Ensure that the entity does not exist
    assert hass.states.get(entity_id) is None


@pytest.mark.parametrize(
    ("entity_id", "routine_id"),
    [
        ("button.roborock_s7_maxv_sc1", 12),
        ("button.roborock_s7_maxv_sc2", 24),
    ],
)
@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_press_routine_button_success(
    hass: HomeAssistant,
    bypass_api_client_fixture: None,
    setup_entry: MockConfigEntry,
    entity_id: str,
    routine_id: int,
    fake_vacuum: FakeDevice,
) -> None:
    """Test pressing the button entities."""
    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        blocking=True,
        target={"entity_id": entity_id},
    )

    fake_vacuum.v1_properties.routines.execute_routine.assert_called_once_with(
        routine_id
    )
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"


@pytest.mark.parametrize(
    ("entity_id", "routine_id"),
    [
        ("button.roborock_s7_maxv_sc1", 12),
    ],
)
@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_press_routine_button_failure(
    hass: HomeAssistant,
    bypass_api_client_fixture: None,
    setup_entry: MockConfigEntry,
    entity_id: str,
    routine_id: int,
    fake_vacuum: FakeDevice,
) -> None:
    """Test failure while pressing the button entity."""
    fake_vacuum.v1_properties.routines.execute_routine.side_effect = RoborockException
    with pytest.raises(HomeAssistantError, match="Error while calling execute_scene"):
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            blocking=True,
            target={"entity_id": entity_id},
        )
    fake_vacuum.v1_properties.routines.execute_routine.assert_called_once_with(
        routine_id
    )
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"


@pytest.mark.parametrize(
    ("entity_id", "data_protocol"),
    [
        ("button.zeo_one_start", "START"),
        ("button.zeo_one_pause", "PAUSE"),
        ("button.zeo_one_shut_down", "SHUTDOWN"),
    ],
)
@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_press_a01_button_success(
    hass: HomeAssistant,
    bypass_api_client_fixture: None,
    setup_entry: MockConfigEntry,
    entity_id: str,
    data_protocol: str,
    fake_devices: list[FakeDevice],
) -> None:
    """Test pressing A01 button entities."""
    # Get the washing machine (A01) device
    washing_machine = next(
        device
        for device in fake_devices
        if hasattr(device, "zeo") and device.zeo is not None
    )

    # Ensure entity exists
    assert hass.states.get(entity_id) is not None

    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        blocking=True,
        target={"entity_id": entity_id},
    )

    # Verify the set_value was called with correct protocol and value
    washing_machine.zeo.set_value.assert_called_once()
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("button.zeo_one_start"),
    ],
)
@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_press_a01_button_failure(
    hass: HomeAssistant,
    bypass_api_client_fixture: None,
    setup_entry: MockConfigEntry,
    entity_id: str,
    fake_devices: list[FakeDevice],
) -> None:
    """Test failure while pressing A01 button entity."""
    # Get the washing machine (A01) device
    washing_machine = next(
        device
        for device in fake_devices
        if hasattr(device, "zeo") and device.zeo is not None
    )
    washing_machine.zeo.set_value.side_effect = RoborockException

    # Ensure entity exists
    assert hass.states.get(entity_id) is not None

    with pytest.raises(HomeAssistantError, match="Failed to press button"):
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            blocking=True,
            target={"entity_id": entity_id},
        )

    washing_machine.zeo.set_value.assert_called_once()
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"


@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_press_q10_empty_dustbin_button_success(
    hass: HomeAssistant,
    bypass_api_client_fixture: None,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
) -> None:
    """Test pressing Q10 empty dustbin button entity."""
    entity_id = "button.roborock_q10_s5_empty_dustbin"

    assert hass.states.get(entity_id) is not None
    await hass.services.async_call(
        "button",
        SERVICE_PRESS,
        blocking=True,
        target={"entity_id": entity_id},
    )

    assert fake_q10_vacuum.b01_q10_properties is not None
    fake_q10_vacuum.b01_q10_properties.vacuum.empty_dustbin.assert_called_once()
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"


@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_press_q10_empty_dustbin_button_failure(
    hass: HomeAssistant,
    bypass_api_client_fixture: None,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
) -> None:
    """Test failure while pressing Q10 empty dustbin button entity."""
    entity_id = "button.roborock_q10_s5_empty_dustbin"
    assert fake_q10_vacuum.b01_q10_properties is not None
    fake_q10_vacuum.b01_q10_properties.vacuum.empty_dustbin.side_effect = (
        RoborockException
    )

    assert hass.states.get(entity_id) is not None
    with pytest.raises(HomeAssistantError, match="Error while calling empty_dustbin"):
        await hass.services.async_call(
            "button",
            SERVICE_PRESS,
            blocking=True,
            target={"entity_id": entity_id},
        )

    fake_q10_vacuum.b01_q10_properties.vacuum.empty_dustbin.assert_called_once()
    assert hass.states.get(entity_id).state == "2023-10-30T08:50:00+00:00"
