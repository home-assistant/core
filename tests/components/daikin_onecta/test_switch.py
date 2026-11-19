"""Tests for Daikin Onecta switch entities."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from daikin_onecta.models import Characteristic
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.climate import ClimateEntityStateAttribute
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

from .platform_helpers import _execute_typed_command
from .test_climate_snapshots import _async_setup_fixture


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
        {ATTR_ENTITY_ID: "switch.test_living_room_econo_mode"},
        blocking=True,
    )

    state = hass.states.get("switch.test_living_room_econo_mode")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SWITCH_SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )
    assert hass.states.get(state.entity_id).state == "on"


async def test_switch_updates_sibling_climate_preset(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A shared preset change immediately reaches the sibling climate entity."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry
    )
    entity_id = "climate.test_living_room_room_temperature"
    assert (
        hass.states.get(entity_id).attributes[ClimateEntityStateAttribute.PRESET_MODE]
        == "eco"
    )

    for service, expected in (
        (SWITCH_SERVICE_TURN_OFF, "none"),
        (SWITCH_SERVICE_TURN_ON, "eco"),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "switch.test_living_room_econo_mode"},
            blocking=True,
        )
        assert (
            hass.states.get(entity_id).attributes[
                ClimateEntityStateAttribute.PRESET_MODE
            ]
            == expected
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
            point.scalar_characteristic("econoMode") is not None
            for point in device.device.management_points
        )
    )
    point = next(
        point
        for point in device.device.management_points
        if point.scalar_characteristic("econoMode") is not None
    )
    characteristic = point.scalar_characteristic("econoMode")
    assert characteristic is not None
    characteristic.value = None
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "switch.test_living_room_econo_mode"},
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
