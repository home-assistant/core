"""Test Roborock Number platform."""

import copy

import pytest
from roborock.exceptions import RoborockException, RoborockTimeout
from roborock.roborock_message import RoborockZeoProtocol
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.components.roborock.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import FakeDevice

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.NUMBER]


@pytest.fixture
def zeo_device(fake_devices: list[FakeDevice]) -> FakeDevice:
    """Get the fake Zeo washing machine device."""
    return next(device for device in fake_devices if getattr(device, "zeo", None))


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_numbers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test number entities and check test values are correctly set."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_entry.entry_id)


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


async def test_zeo_delay_start(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    zeo_device: FakeDevice,
) -> None:
    """Test setting the delay start timer on a Zeo washing machine."""
    entity_id = entity_registry.async_get_entity_id(
        "number", DOMAIN, "zeo_delay_start_zeo_duid"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id) is not None

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 180.0},
        blocking=True,
        target={"entity_id": entity_id},
    )

    assert zeo_device.zeo
    zeo_device.zeo.set_value.assert_awaited_once_with(
        RoborockZeoProtocol.COUNTDOWN,
        180,
    )


async def test_zeo_delay_start_update_failed(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    zeo_device: FakeDevice,
) -> None:
    """Test a failure while setting the delay start timer on a Zeo device."""
    assert zeo_device.zeo
    zeo_device.zeo.set_value.side_effect = RoborockException
    entity_id = entity_registry.async_get_entity_id(
        "number", DOMAIN, "zeo_delay_start_zeo_duid"
    )
    assert entity_id is not None

    with pytest.raises(HomeAssistantError, match="Failed to update Roborock options"):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            service_data={ATTR_VALUE: 180.0},
            blocking=True,
            target={"entity_id": entity_id},
        )


async def test_zeo_delay_start_absent_without_schema(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_devices: list[FakeDevice],
) -> None:
    """Test the delay start entity is not created when the schema lacks DP 217."""
    zeo_device_1 = next(
        (device for device in fake_devices if device.zeo is not None),
        None,
    )
    assert zeo_device_1 is not None

    zeo_device_2 = copy.deepcopy(zeo_device_1)
    zeo_device_2.device_info.duid = "zeo_duid_2"
    zeo_device_2._duid = "zeo_duid_2"
    zeo_device_2.device_info.name = "Zeo Two"
    zeo_device_2._name = "Zeo Two"
    zeo_device_2.device_info.sn = "zeo_sn_2"

    # Exclude the countdown parameter: 217 (COUNTDOWN)
    zeo_device_2.product.schema = [
        schema for schema in zeo_device_2.product.schema if schema.id != "217"
    ]

    fake_devices.append(zeo_device_2)

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("number.zeo_one_delay_start") is not None
    assert hass.states.get("number.zeo_two_delay_start") is None
