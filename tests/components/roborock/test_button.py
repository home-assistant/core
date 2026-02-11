"""Test Roborock Button platform."""

from unittest.mock import Mock

import pytest
from roborock import RoborockException
from roborock.exceptions import RoborockTimeout

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import FakeDevice

from tests.common import MockConfigEntry


@pytest.fixture
def get_scenes_failure_fixture(fake_vacuum: FakeDevice) -> None:
    """Fixture to raise when getting scenes."""
    fake_vacuum.v1_properties.routines.get_routines.side_effect = RoborockException


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.BUTTON]


@pytest.fixture(name="consumeables_trait", autouse=True)
def consumeables_trait_fixture(fake_vacuum: FakeDevice) -> Mock:
    """Get the fake vacuum device command trait for asserting that commands happened."""
    assert fake_vacuum.v1_properties is not None
    return fake_vacuum.v1_properties.consumables


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("button.roborock_s7_maxv_reset_sensor_consumable"),
        ("button.roborock_s7_maxv_reset_air_filter_consumable"),
        ("button.roborock_s7_maxv_reset_side_brush_consumable"),
        ("button.roborock_s7_maxv_reset_main_brush_consumable"),
    ],
)
@pytest.mark.freeze_time("2023-10-30 08:50:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_success(
    hass: HomeAssistant,
    bypass_api_client_fixture: None,
    setup_entry: MockConfigEntry,
    entity_id: str,
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
    assert consumeables_trait.reset_consumable.assert_called_once
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
