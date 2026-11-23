"""Tests for Daikin Onecta switch entities."""

from daikin_onecta.models import Characteristic, ManagementPoint
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF as SWITCH_SERVICE_TURN_OFF,
    SERVICE_TURN_ON as SWITCH_SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import MockOnectaClient
from .platform_helpers import (
    _async_setup_fixture,
    _execute_typed_command,
    _load_gateway_devices,
)

TEST_LIVING_ROOM_STREAMER_MODE_ENTITY_ID = "switch.test_living_room_streamer_mode"


async def test_switch_service_updates_cached_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """A successful switch command updates the state without a cloud refresh."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SWITCH_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_LIVING_ROOM_STREAMER_MODE_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(TEST_LIVING_ROOM_STREAMER_MODE_ENTITY_ID)
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SWITCH_SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )
    assert hass.states.get(state.entity_id).state == "on"


async def test_econo_mode_is_only_exposed_as_climate_preset(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Avoid exposing econo mode as both a switch and a climate preset."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    assert hass.states.get("climate.test_living_room_room_temperature") is not None
    assert hass.states.get("switch.test_living_room_econo_mode") is None


async def test_settable_climate_power_without_setpoint_is_exposed_as_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Expose writable power when the climate point has no supported setpoint."""
    gateway_devices = _load_gateway_devices("climate_floorheatingairflow")
    gateway = gateway_devices[0]
    gateway.management_points.append(
        ManagementPoint(
            embedded_id="climatePowerWithoutSetpoint",
            management_point_type="climateControl",
            characteristics={
                "onOffMode": Characteristic(
                    value="on", settable=True, values=["on", "off"]
                )
            },
        )
    )
    await _async_setup_fixture(
        hass,
        config_entry,
        "climate_floorheatingairflow",
        gateway_devices=gateway_devices,
    )
    execute_command = _execute_typed_command(config_entry, mock_onecta_client)
    config_entry.runtime_data.async_execute_command = execute_command

    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN,
        DOMAIN,
        f"{gateway.id}_climatePowerWithoutSetpoint_onOffMode",
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SWITCH_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == "off"
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway.id,
        "climatePowerWithoutSetpoint",
        "onOffMode",
        "off",
        path=None,
    )


@pytest.mark.parametrize("service", [SWITCH_SERVICE_TURN_ON, SWITCH_SERVICE_TURN_OFF])
async def test_switch_rejects_unknown_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    service: str,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reject switch commands through the HA service when Daikin omits its value."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    execute_command = _execute_typed_command(config_entry, mock_onecta_client)
    config_entry.runtime_data.async_execute_command = execute_command
    device = next(
        device
        for device in config_entry.runtime_data.data.values()
        if any(
            point.scalar_characteristic("streamerMode") is not None
            for point in device.device.management_points
        )
    )
    point = next(
        point
        for point in device.device.management_points
        if point.scalar_characteristic("streamerMode") is not None
    )
    characteristic = point.scalar_characteristic("streamerMode")
    assert characteristic is not None
    characteristic.value = None
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: TEST_LIVING_ROOM_STREAMER_MODE_ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_key == "switch_state_unavailable"
    execute_command.assert_not_awaited()


async def test_unknown_characteristic_is_skipped(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Do not create untranslated switches for unknown characteristics."""
    gateway_devices = _load_gateway_devices("minimal_data")
    point = gateway_devices[0].management_points_by_type("climateControl")[0]
    point.characteristics["futureCharacteristic"] = Characteristic(
        value="on", settable=True, values=["on", "off"]
    )

    await _async_setup_fixture(
        hass, config_entry, "minimal_data", gateway_devices=gateway_devices
    )

    assert (
        entity_registry.async_get_entity_id(
            SWITCH_DOMAIN,
            DOMAIN,
            f"{gateway_devices[0].id}_{point.embedded_id}_futureCharacteristic",
        )
        is None
    )
