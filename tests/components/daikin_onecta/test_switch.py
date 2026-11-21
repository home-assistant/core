"""Tests for Daikin Onecta switch entities."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from daikin_onecta.models import Characteristic, ManagementPoint
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.switch import (
    async_setup_entry as async_setup_switches,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF as SWITCH_SERVICE_TURN_OFF,
    SERVICE_TURN_ON as SWITCH_SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .platform_helpers import (
    _async_setup_fixture,
    _execute_typed_command,
    _load_gateway_devices,
)

TEST_LIVING_ROOM_STREAMER_MODE_ENTITY_ID = "switch.test_living_room_streamer_mode"


async def test_switch_service_updates_cached_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A successful switch command updates the state without a cloud refresh."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry
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
    execute_command = _execute_typed_command(config_entry)
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
    config_entry.runtime_data.client.patch_characteristic.assert_awaited_once_with(
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
) -> None:
    """Reject switch commands through the HA service when Daikin omits its value."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    execute_command = _execute_typed_command(config_entry)
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


async def test_unknown_characteristic_is_skipped(hass: HomeAssistant) -> None:
    """Do not create untranslated switches for unknown characteristics."""
    management_point = SimpleNamespace(
        embedded_id="point",
        management_point_type="futureType",
        scalar_characteristics=lambda: {
            "futureCharacteristic": Characteristic(
                value="on", settable=True, values=["on", "off"]
            )
        },
    )
    device = SimpleNamespace(
        device=SimpleNamespace(management_points=[management_point]),
        present_in_cloud=True,
    )
    coordinator = SimpleNamespace(
        data={"gateway": device},
        cloud_update_sequence=1,
        async_add_listener=MagicMock(return_value=MagicMock()),
    )
    config_entry = SimpleNamespace(
        runtime_data=coordinator, async_on_unload=MagicMock()
    )
    async_add_entities = MagicMock()

    await async_setup_switches(hass, config_entry, async_add_entities)

    async_add_entities.assert_not_called()
