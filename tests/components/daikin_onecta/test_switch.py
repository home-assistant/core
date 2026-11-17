"""Tests for Daikin Onecta switch entities."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta.models import Characteristic
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.climate import ClimateEntityStateAttribute
from homeassistant.components.daikin_onecta.switch import (
    DaikinSwitch,
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
        {ATTR_ENTITY_ID: "switch.test_living_room_climatecontrol_econo_mode"},
        blocking=True,
    )

    state = hass.states.get("switch.test_living_room_climatecontrol_econo_mode")
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
            {ATTR_ENTITY_ID: "switch.test_living_room_climatecontrol_econo_mode"},
            blocking=True,
        )
        assert (
            hass.states.get(entity_id).attributes[
                ClimateEntityStateAttribute.PRESET_MODE
            ]
            == expected
        )


def test_switch_preserves_unknown_state() -> None:
    """Do not interpret an omitted switch value as off."""
    entity = object.__new__(DaikinSwitch)
    entity._switch_state = None

    assert entity.is_on is None


@pytest.mark.parametrize("method", ["async_turn_on", "async_turn_off"])
async def test_switch_rejects_unknown_state(method: str) -> None:
    """Reject switch commands when Daikin omits the current value."""
    entity = object.__new__(DaikinSwitch)
    object.__setattr__(entity, "_device", MagicMock(name="Device"))
    entity._switch_state = None
    entity._async_execute_command = AsyncMock()

    with pytest.raises(ServiceValidationError) as err:
        await getattr(entity, method)()

    assert err.value.translation_key == "switch_state_unavailable"
    entity._async_execute_command.assert_not_awaited()


async def test_switch_setup_skips_builtin_power_controls() -> None:
    """Keep climate and water-heater power controls on their native platforms."""
    management_point = SimpleNamespace(
        embedded_id="point",
        management_point_type="climateControl",
        scalar_characteristics=lambda: {
            "onOffMode": Characteristic(
                value="on", settable=True, values=["on", "off"]
            ),
            "powerfulMode": Characteristic(
                value="off", settable=True, values=["on", "off"]
            ),
        },
    )
    device = SimpleNamespace(
        device=SimpleNamespace(management_points=[management_point])
    )
    config_entry = SimpleNamespace(
        runtime_data=SimpleNamespace(data={"gateway": device})
    )
    async_add_entities = MagicMock()

    with patch(
        "homeassistant.components.daikin_onecta.switch.SWITCH_DESCRIPTIONS",
        {"onOffMode": MagicMock(), "powerfulMode": MagicMock()},
    ):
        await async_setup_switches(MagicMock(), config_entry, async_add_entities)

    async_add_entities.assert_called_once_with([])


async def test_unknown_characteristic_is_skipped() -> None:
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
        device=SimpleNamespace(management_points=[management_point])
    )
    config_entry = SimpleNamespace(
        runtime_data=SimpleNamespace(data={"gateway": device})
    )
    async_add_entities = MagicMock()

    await async_setup_switches(MagicMock(), config_entry, async_add_entities)

    async_add_entities.assert_called_once_with([])
