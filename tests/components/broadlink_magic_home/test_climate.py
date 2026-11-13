"""Tests for Broadlink Magic Home air conditioners."""

from unittest.mock import AsyncMock

from broadlink_magic import (
    AC_MODE_COOL,
    AC_MODE_HEAT,
    DiscoveredRMMax,
    Family,
    ImportedDevice,
    RMProfile,
    encode_ac_attribute,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.broadlink_magic_home.const import DOMAIN
from homeassistant.components.broadlink_magic_home.helpers import family_to_entry_data
from homeassistant.components.climate import HVACMode
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from . import setup_integration

pytestmark = pytest.mark.usefixtures("socket_enabled")

AIR_CONDITIONER = "climate.whole_home_air_conditioner"


async def test_air_conditioner_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test the imported air conditioner and its room."""
    await setup_integration(hass, config_entry)

    state = hass.states.get(AIR_CONDITIONER)
    assert state is not None
    assert state.attributes["target_temp_step"] == 1.0
    entity = entity_registry.async_get(AIR_CONDITIONER)
    assert entity is not None
    assert entity.device_id is not None
    device = device_registry.async_get(entity.device_id)
    assert device is not None
    whole_home_area = area_registry.async_get_area_by_name("Whole home")
    assert whole_home_area is not None
    assert device.area_id == whole_home_area.id


async def test_air_conditioner_commands_and_reports(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_send: AsyncMock,
) -> None:
    """Test air conditioner commands and gateway status reports."""
    coordinator = await setup_integration(hass, config_entry)

    coordinator._handle_fastcon_report(6, b"\x01\x02\x1a\x03")
    await hass.async_block_till_done()
    assert hass.states.get(AIR_CONDITIONER).attributes["temperature"] == 26

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: AIR_CONDITIONER, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    assert mock_send.await_args.args[0] == 6
    assert mock_send.await_args.args[1] == [b"\x00\x01\x01", b"\x01\x01\x02"]
    coordinator._handle_fastcon_report(6, b"\x00\x02\x1b\x01")
    await hass.async_block_till_done()
    assert hass.states.get(AIR_CONDITIONER).state == HVACMode.COOL

    mock_send.reset_mock()
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: AIR_CONDITIONER, "temperature": 26},
        blocking=True,
    )
    assert mock_send.await_args.args[1] == [b"\x02\x01\x1a"]

    mock_send.reset_mock()
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {ATTR_ENTITY_ID: AIR_CONDITIONER, "fan_mode": "high"},
        blocking=True,
    )
    assert mock_send.await_args.args[1] == [b"\x03\x01\x03"]

    mock_send.reset_mock()
    await hass.services.async_call(
        "climate", "turn_off", {ATTR_ENTITY_ID: AIR_CONDITIONER}, blocking=True
    )
    assert mock_send.await_args.args[1] == [b"\x00\x01\x00"]
    coordinator._handle_fastcon_report(6, b"\x01\x02\x1a\x03")
    await hass.async_block_till_done()
    assert hass.states.get(AIR_CONDITIONER).state == HVACMode.OFF


async def test_turn_on_restores_last_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_send: AsyncMock,
) -> None:
    """Test turning on uses the last reported or commanded mode."""
    coordinator = await setup_integration(hass, config_entry)

    coordinator._handle_fastcon_report(6, bytes([0, AC_MODE_COOL, 26, 0]))
    await hass.async_block_till_done()
    await hass.services.async_call(
        "climate", "turn_on", {ATTR_ENTITY_ID: AIR_CONDITIONER}, blocking=True
    )
    assert mock_send.await_args.args[1] == [
        encode_ac_attribute("power", 1),
        encode_ac_attribute("mode", AC_MODE_COOL),
    ]

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: AIR_CONDITIONER, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    await hass.services.async_call(
        "climate", "turn_off", {ATTR_ENTITY_ID: AIR_CONDITIONER}, blocking=True
    )
    await hass.services.async_call(
        "climate", "turn_on", {ATTR_ENTITY_ID: AIR_CONDITIONER}, blocking=True
    )
    assert mock_send.await_args.args[1] == [
        encode_ac_attribute("power", 1),
        encode_ac_attribute("mode", AC_MODE_HEAT),
    ]
    assert hass.states.get(AIR_CONDITIONER).state == HVACMode.HEAT


async def test_pending_command_needs_new_device_report(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_send: AsyncMock,
) -> None:
    """Test only a newer report of the device confirms a pending command."""
    coordinator = await setup_integration(hass, config_entry)
    coordinator._handle_fastcon_report(6, bytes([1, AC_MODE_COOL, 24, 3]))
    await hass.async_block_till_done()

    for temperature in (26, 24):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {ATTR_ENTITY_ID: AIR_CONDITIONER, "temperature": temperature},
            blocking=True,
        )
    coordinator.async_set_updated_data(coordinator.gateway_set)
    coordinator._handle_fastcon_report(6, bytes([1, AC_MODE_COOL, 26, 3]))
    await hass.async_block_till_done()
    assert hass.states.get(AIR_CONDITIONER).attributes["temperature"] == 24

    coordinator._handle_fastcon_report(6, bytes([1, AC_MODE_COOL, 24, 3]))
    coordinator._handle_fastcon_report(6, bytes([1, AC_MODE_COOL, 27, 3]))
    await hass.async_block_till_done()
    assert hass.states.get(AIR_CONDITIONER).attributes["temperature"] == 27


async def test_air_conditioner_command_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_send: AsyncMock,
) -> None:
    """Test commands fail for devices without an address or offline gateways."""
    coordinator = await setup_integration(hass, config_entry)

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_send_ac(
            ImportedDevice(did="missing", pid="", name="Missing"), [("power", 1)]
        )
    assert err.value.translation_key == "device_not_addressable"

    mock_send.return_value = 0
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "climate", "turn_on", {ATTR_ENTITY_ID: AIR_CONDITIONER}, blocking=True
        )
    assert err.value.translation_key == "gateway_offline"
    assert hass.states.get(AIR_CONDITIONER).state == HVACMode.OFF


async def test_rm_air_conditioner(
    hass: HomeAssistant,
    family: Family,
    gateways: list[DiscoveredRMMax],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_send: AsyncMock,
) -> None:
    """Test an infrared air conditioner learned on the RM MAX gateway."""
    family.devices.append(
        ImportedDevice(
            did="00000000000000000000aabbccddeeff",
            pid="",
            name="Bedroom air conditioner",
            sdid="aabbccddeeff_3",
            spid="0000000000000000000000008fab0000",
            short_addr=4662,
            room_id=1,
            is_rm_child=True,
            rm_profile=RMProfile.AC,
        )
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=family.family_id,
        title=family.name,
        data=family_to_entry_data(family, gateways),
    )
    await setup_integration(hass, config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "climate", DOMAIN, "family-1_aabbccddeeff_3"
    )
    assert entity_id is not None
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "rm:aabbccddeeff_3"), config_entry_id=config_entry.entry_id
    )
    assert device is not None
    assert device.model == "Magic Home RM Air Conditioner"

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: entity_id, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    assert mock_send.await_args.args == (4662, [b"\x00\x01\x01", b"\x01\x01\x01"])
    assert hass.states.get(entity_id).state == HVACMode.HEAT
