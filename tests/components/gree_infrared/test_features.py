"""Tests for the newly wired Gree fields: swing, vane, sleep, ifeel, fresh air, timer."""

from infrared_protocols.commands.gree_ac import (
    GreeAcCommand,
    GreeAcFreshAir,
    GreeAcModel,
)
import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.gree_infrared import PLATFORMS
from homeassistant.components.gree_infrared.const import (
    CONF_GENERIC_OPTIONS,
    CONF_HVAC_MODES,
    CONF_MODEL,
    DOMAIN,
    MODEL_GENERIC,
    MODEL_YAP1F,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import ENTRY_ID

from tests.common import MockConfigEntry, mock_restore_cache_with_extra_data
from tests.components.infrared.common import MockInfraredEmitterEntity

_CLIMATE = "climate.gree_ac"


@pytest.fixture
def extra_entry_data(
    hvac_modes: list[HVACMode], request: pytest.FixtureRequest
) -> dict:
    """Default to YAP1F; generic cases pass explicit params."""
    return getattr(
        request, "param", {CONF_HVAC_MODES: hvac_modes, CONF_MODEL: MODEL_YAP1F}
    )


def _entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{ENTRY_ID}_{key}"
    )
    assert entity_id is not None
    return entity_id


def _last_command(emitter: MockInfraredEmitterEntity) -> GreeAcCommand:
    command = emitter.send_command_calls[-1]
    assert isinstance(command, GreeAcCommand)
    return command


async def _turn_on_cool(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )


@pytest.mark.usefixtures("init_integration")
async def test_vertical_and_horizontal_swing(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Swing services land in the emitted command."""
    await _turn_on_cool(hass)
    await hass.services.async_call(
        "climate",
        "set_swing_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "swing_mode": "on"},
        blocking=True,
    )
    await hass.services.async_call(
        "climate",
        "set_swing_horizontal_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "swing_horizontal_mode": "on"},
        blocking=True,
    )
    command = _last_command(mock_infrared_emitter_entity)
    assert (command.swing_v, command.swing_h) == (True, True)
    state = hass.states.get(_CLIMATE)
    assert state is not None
    assert state.attributes["swing_mode"] == "on"
    assert state.attributes["swing_horizontal_mode"] == "on"


@pytest.mark.usefixtures("init_integration")
async def test_vane_position_select_yap1f(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """A fixed vane position parks the vane and clears sweep."""
    await _turn_on_cool(hass)
    entity_id = _entity_id(hass, "select", "swing_v_position")
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, "option": "3"},
        blocking=True,
    )
    command = _last_command(mock_infrared_emitter_entity)
    assert command.swing_v_position == 3
    assert hass.states.get(entity_id).state == "3"


@pytest.mark.usefixtures("init_integration")
async def test_yap1f_horizontal_position_and_display_controls(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """YAP1F select controls set exact protocol fields."""
    await _turn_on_cool(hass)
    for key, option, field, expected in (
        ("swing_h_position", "max_right", "swing_h_position", 6),
        ("display_temp", "outdoor", "display_temp", 3),
        ("fahrenheit", "fahrenheit", "fahrenheit", True),
    ):
        entity_id = _entity_id(hass, "select", key)
        await hass.services.async_call(
            "select",
            "select_option",
            {ATTR_ENTITY_ID: entity_id, "option": option},
            blocking=True,
        )
        assert getattr(_last_command(mock_infrared_emitter_entity), field) == expected

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: _CLIMATE, "temperature": 24},
        blocking=True,
    )
    command = _last_command(mock_infrared_emitter_entity)
    assert command.fahrenheit is True
    assert command.temperature == 75


@pytest.mark.usefixtures("init_integration")
async def test_econo_switch_cool_only_and_cancel_on_mode_change(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Econo is available only in cool and clears when leaving cool."""
    await _turn_on_cool(hass)
    entity_id = _entity_id(hass, "switch", "econo")
    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert _last_command(mock_infrared_emitter_entity).econo is True
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.DRY},
        blocking=True,
    )
    assert _last_command(mock_infrared_emitter_entity).econo is False
    assert hass.states.get(entity_id).state == "unavailable"


@pytest.mark.usefixtures("init_integration")
async def test_sleep_switch_and_cancel_on_mode_change(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Sleep sends while cool and is cancelled by a mode change and off."""
    await _turn_on_cool(hass)
    entity_id = _entity_id(hass, "switch", "sleep")
    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert _last_command(mock_infrared_emitter_entity).sleep is True
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.DRY},
        blocking=True,
    )
    command = _last_command(mock_infrared_emitter_entity)
    assert command.sleep is False
    assert hass.states.get(entity_id).state == "off"


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("hvac_modes", [[HVACMode.COOL, HVACMode.AUTO]])
async def test_sleep_blocked_in_auto(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Sleep is unavailable in auto mode and rejected by the climate owner."""
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.AUTO},
        blocking=True,
    )
    entity_id = _entity_id(hass, "switch", "sleep")
    assert hass.states.get(entity_id).state == "unavailable"
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    with pytest.raises(HomeAssistantError):
        await climate.async_set_option("sleep", True)
    assert mock_infrared_emitter_entity.send_command_calls[-1].sleep is False


@pytest.mark.usefixtures("init_integration")
async def test_ifeel_switch(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """IFeel lands in the emitted YAP1F command."""
    await _turn_on_cool(hass)
    entity_id = _entity_id(hass, "switch", "ifeel")
    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert _last_command(mock_infrared_emitter_entity).ifeel is True


@pytest.mark.usefixtures("init_integration")
async def test_fresh_air_select(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Fresh-air levels land in the emitted command."""
    await _turn_on_cool(hass)
    entity_id = _entity_id(hass, "select", "fresh_air")
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id, "option": "level_2"},
        blocking=True,
    )
    assert (
        _last_command(mock_infrared_emitter_entity).fresh_air is GreeAcFreshAir.LEVEL_2
    )


@pytest.mark.usefixtures("init_integration")
async def test_timer_number(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Timer values land in the emitted command; 0 means off."""
    await _turn_on_cool(hass)
    entity_id = _entity_id(hass, "number", "timer_hours")
    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: entity_id, "value": 2.5}, blocking=True
    )
    assert _last_command(mock_infrared_emitter_entity).timer_hours == 2.5
    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: entity_id, "value": 0}, blocking=True
    )
    assert _last_command(mock_infrared_emitter_entity).timer_hours is None


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_new_fields_restore_after_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """All new fields restore and are used by the next send."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    _CLIMATE,
                    HVACMode.OFF,
                    {
                        "temperature": 24,
                        "fan_mode": "auto",
                        "swing_mode": "on",
                        "swing_horizontal_mode": "on",
                    },
                ),
                {
                    "last_active_hvac_mode": HVACMode.COOL.value,
                    "turbo": False,
                    "light": True,
                    "health": False,
                    "xfan": False,
                    "sleep": True,
                    "ifeel": True,
                    "swing_v": True,
                    "swing_h": True,
                    "swing_v_position": 3,
                    "fresh_air": int(GreeAcFreshAir.LEVEL_1),
                    "timer_hours": 1.5,
                    "swing_h_position": 4,
                    "econo": True,
                    "fahrenheit": True,
                    "display_temp": 3,
                },
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_infrared_emitter_entity.send_command_calls == []
    state = mock_config_entry.runtime_data
    assert (state.swing_v, state.swing_h) == (True, True)
    assert state.swing_v_position == 3
    assert state.sleep is True
    assert state.ifeel is True
    assert state.fresh_air == int(GreeAcFreshAir.LEVEL_1)
    assert state.timer_hours == 1.5
    assert state.swing_h_position == 4
    assert state.econo is True
    assert state.fahrenheit is True
    assert state.display_temp == 3
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    command = _last_command(mock_infrared_emitter_entity)
    assert command.model is GreeAcModel.YAP1F
    assert (command.swing_v, command.swing_h) == (True, True)
    assert command.swing_v_position == 3
    assert command.sleep is True
    assert command.ifeel is True
    assert command.fresh_air is GreeAcFreshAir.LEVEL_1
    assert command.timer_hours == 1.5
    assert command.swing_h_position == 4
    assert command.econo is True
    assert command.fahrenheit is True
    assert command.display_temp == 3


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "extra_entry_data",
    [
        {
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
            CONF_MODEL: MODEL_GENERIC,
            CONF_GENERIC_OPTIONS: True,
        }
    ],
    indirect=True,
)
async def test_generic_new_fields_send(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Generic carries swing, sleep, fresh air and timer in its own frame."""
    await _turn_on_cool(hass)
    await hass.services.async_call(
        "climate",
        "set_swing_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "swing_mode": "on"},
        blocking=True,
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {
            ATTR_ENTITY_ID: _entity_id(hass, "select", "fresh_air"),
            "option": "level_1",
        },
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: _entity_id(hass, "number", "timer_hours"), "value": 1.0},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: _entity_id(hass, "switch", "sleep")},
        blocking=True,
    )
    command = _last_command(mock_infrared_emitter_entity)
    assert command.model is GreeAcModel.GENERIC
    assert command.swing_v is True
    assert command.sleep is True
    assert command.fresh_air is GreeAcFreshAir.LEVEL_1
    assert command.timer_hours == 1.0
    assert command.swing_v_position is None
    assert command.ifeel is False


async def test_platforms_include_new_entities(hass: HomeAssistant) -> None:
    """Sanity check that select/number platforms are wired."""
    assert set(PLATFORMS) >= {
        Platform.CLIMATE,
        Platform.SWITCH,
        Platform.SELECT,
        Platform.NUMBER,
    }
