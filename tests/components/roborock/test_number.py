"""Test Roborock Number platform."""

import pytest
from roborock.exceptions import RoborockTimeout

from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import FakeDevice

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.NUMBER]


async def test_update_sound_volume(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test allowed changing values for number entities."""

    # Ensure that the entity exist, as these test can pass even if there is no entity.
    state = hass.states.get("number.roborock_s7_maxv_volume")
    assert state is not None
    assert state.state == "50.0"

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 3.0},
        blocking=True,
        target={"entity_id": "number.roborock_s7_maxv_volume"},
    )

    assert fake_vacuum.v1_properties is not None
    assert fake_vacuum.v1_properties.sound_volume.set_volume.call_count == 1
    assert fake_vacuum.v1_properties.sound_volume.set_volume.call_args[0] == (3.0,)

    # Verify the entity state is updated with the latest information from the trait
    state = hass.states.get("number.roborock_s7_maxv_volume")
    assert state is not None
    assert state.state == "3.0"


async def test_q10_update_sound_volume(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
) -> None:
    """Test changing the volume of a Q10 device."""
    entity_id = "number.roborock_q10_s5_volume"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "50.0"

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 30.0},
        blocking=True,
        target={"entity_id": entity_id},
    )

    assert fake_q10_vacuum.b01_q10_properties is not None
    fake_q10_vacuum.b01_q10_properties.volume.set_volume.assert_awaited_once_with(30)

    # The trait listener pushes the new value into the entity state
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "30.0"


async def test_q10_volume_unknown_value(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
) -> None:
    """Test the Q10 entity reports unknown when the trait value is None."""
    assert fake_q10_vacuum.b01_q10_properties is not None
    fake_q10_vacuum.b01_q10_properties.volume.volume = None

    await async_update_entity(hass, "number.roborock_q10_s5_volume")

    state = hass.states.get("number.roborock_q10_s5_volume")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_q10_volume_update_failed(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
) -> None:
    """Test a failure while changing the volume of a Q10 device."""
    assert fake_q10_vacuum.b01_q10_properties is not None
    fake_q10_vacuum.b01_q10_properties.volume.set_volume.side_effect = RoborockTimeout

    assert hass.states.get("number.roborock_q10_s5_volume") is not None

    with pytest.raises(HomeAssistantError, match="Failed to update Roborock options"):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            service_data={ATTR_VALUE: 30.0},
            blocking=True,
            target={"entity_id": "number.roborock_q10_s5_volume"},
        )

    fake_q10_vacuum.b01_q10_properties.volume.set_volume.assert_awaited_once_with(30)


async def test_volume_unknown_value(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test the entity reports unknown when the trait value is None."""
    assert fake_vacuum.v1_properties is not None
    fake_vacuum.v1_properties.sound_volume.volume = None

    await async_update_entity(hass, "number.roborock_s7_maxv_volume")

    state = hass.states.get("number.roborock_s7_maxv_volume")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_volume_update_failed(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test allowed changing values for number entities."""
    assert fake_vacuum.v1_properties is not None
    fake_vacuum.v1_properties.sound_volume.set_volume.side_effect = RoborockTimeout

    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get("number.roborock_s7_maxv_volume") is not None

    with pytest.raises(HomeAssistantError, match="Failed to update Roborock options"):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            service_data={ATTR_VALUE: 3.0},
            blocking=True,
            target={"entity_id": "number.roborock_s7_maxv_volume"},
        )

    assert fake_vacuum.v1_properties.sound_volume.set_volume.call_count == 1
    assert fake_vacuum.v1_properties.sound_volume.set_volume.call_args[0] == (3.0,)
