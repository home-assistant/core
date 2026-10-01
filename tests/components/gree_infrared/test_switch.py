"""Behavior tests for the YAP1F profile and its shared option switches."""

import asyncio
from unittest.mock import patch

from infrared_protocols.commands.gree_ac import (
    GreeAcCommand,
    GreeAcFanSpeed,
    GreeAcMode,
    GreeAcModel,
)
import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.gree_infrared.const import (
    CONF_GENERIC_OPTIONS,
    CONF_HVAC_MODES,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    CONF_MODEL,
    DOMAIN,
    MODEL_GENERIC,
    MODEL_YAP1F,
)
from homeassistant.components.infrared import DATA_COMPONENT, InfraredReceivedSignal
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import ENTRY_ID

from tests.common import MockConfigEntry, mock_restore_cache_with_extra_data
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)

_CLIMATE = "climate.gree_ac"


def _option_entity_id(hass: HomeAssistant, key: str) -> str:
    """Resolve an option independently of its translated display name."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "switch", DOMAIN, f"{ENTRY_ID}_{key}"
    )
    assert entity_id is not None
    return entity_id


@pytest.fixture
def extra_entry_data(
    hvac_modes: list[HVACMode], request: pytest.FixtureRequest
) -> dict:
    """Use requested test profile, defaulting to the established YAP1F case."""
    return getattr(
        request, "param", {CONF_HVAC_MODES: hvac_modes, CONF_MODEL: MODEL_YAP1F}
    )


def _last_command(emitter: MockInfraredEmitterEntity) -> GreeAcCommand:
    """Return the most recently emitted full-state command."""
    command = emitter.send_command_calls[-1]
    assert isinstance(command, GreeAcCommand)
    return command


@pytest.mark.usefixtures("init_integration")
async def test_option_switches_preserve_complete_state(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Feature switches combine with later temperature and fan changes."""
    assert hass.states.get(_option_entity_id(hass, "light")).state == "on"
    assert mock_infrared_emitter_entity.send_command_calls == []
    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: _option_entity_id(hass, "turbo")},
        blocking=True,
    )
    assert mock_infrared_emitter_entity.send_command_calls == []
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: _option_entity_id(hass, "light")},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: _option_entity_id(hass, "health")},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: _option_entity_id(hass, "xfan")},
        blocking=True,
    )
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: _CLIMATE, ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "fan_mode": "high"},
        blocking=True,
    )
    command = _last_command(mock_infrared_emitter_entity)
    assert (command.model, command.mode, command.temperature, command.fan) == (
        GreeAcModel.YAP1F,
        GreeAcMode.COOL,
        25,
        GreeAcFanSpeed.HIGH,
    )
    assert (command.turbo, command.display, command.anion, command.blow) == (
        True,
        False,
        True,
        True,
    )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "extra_entry_data",
    [{CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY], CONF_MODEL: MODEL_GENERIC}],
    indirect=True,
)
async def test_generic_options_remain_hidden_by_default(hass: HomeAssistant) -> None:
    """Generic entries keep their established option-free defaults."""
    assert (
        er.async_get(hass).async_get_entity_id("switch", DOMAIN, f"{ENTRY_ID}_light")
        is None
    )


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
async def test_generic_option_switches_preserve_full_state(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """The opt-in exposes flags without changing Generic wire encoding."""
    assert _option_entity_id(hass, "light")
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: _option_entity_id(hass, "light")},
        blocking=True,
    )
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: _CLIMATE, ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "fan_mode": "high"},
        blocking=True,
    )
    command = _last_command(mock_infrared_emitter_entity)
    assert command.model is GreeAcModel.GENERIC
    assert (
        command.temperature,
        command.fan,
        command.display,
        command.turbo,
        command.anion,
        command.blow,
    ) == (25, GreeAcFanSpeed.HIGH, False, False, False, False)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("extra_entry_data", "expected_model"),
    [
        (
            {CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY], CONF_MODEL: MODEL_YAP1F},
            GreeAcModel.YAP1F,
        ),
        (
            {
                CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
                CONF_MODEL: MODEL_GENERIC,
                CONF_GENERIC_OPTIONS: True,
            },
            GreeAcModel.GENERIC,
        ),
    ],
    indirect=["extra_entry_data"],
    ids=["yap1f", "generic-options"],
)
async def test_failed_send_does_not_commit_option_or_temperature(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    expected_model: GreeAcModel,
) -> None:
    """A failed IR transmission leaves every assumed state field intact."""
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    with patch.object(
        mock_infrared_emitter_entity,
        "async_send_command",
        side_effect=HomeAssistantError,
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {ATTR_ENTITY_ID: _option_entity_id(hass, "turbo")},
                blocking=True,
            )
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "climate",
                "set_temperature",
                {ATTR_ENTITY_ID: _CLIMATE, ATTR_TEMPERATURE: 25},
                blocking=True,
            )
    assert hass.states.get(_CLIMATE).attributes["temperature"] == 16
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "fan_mode": "high"},
        blocking=True,
    )
    assert hass.states.get(_option_entity_id(hass, "turbo")).state == "off"
    command = _last_command(mock_infrared_emitter_entity)
    assert command.model is expected_model
    assert (command.temperature, command.turbo) == (16, False)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("extra_entry_data", "expected_model"),
    [
        (
            {CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY], CONF_MODEL: MODEL_YAP1F},
            GreeAcModel.YAP1F,
        ),
        (
            {
                CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
                CONF_MODEL: MODEL_GENERIC,
                CONF_GENERIC_OPTIONS: True,
            },
            GreeAcModel.GENERIC,
        ),
    ],
    indirect=["extra_entry_data"],
    ids=["yap1f", "generic-options"],
)
async def test_concurrent_changes_compose_under_one_lock(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    expected_model: GreeAcModel,
) -> None:
    """A queued option edit cannot be lost behind an in-flight climate send."""
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    started, release = asyncio.Event(), asyncio.Event()
    original_send = mock_infrared_emitter_entity.async_send_command

    async def slow_send(command: GreeAcCommand) -> None:
        started.set()
        await release.wait()
        await original_send(command)

    with patch.object(
        mock_infrared_emitter_entity, "async_send_command", side_effect=slow_send
    ):
        first = asyncio.create_task(
            hass.services.async_call(
                "switch",
                "turn_on",
                {ATTR_ENTITY_ID: _option_entity_id(hass, "turbo")},
                blocking=True,
            )
        )
        await started.wait()
        second = asyncio.create_task(
            hass.services.async_call(
                "climate",
                "set_temperature",
                {ATTR_ENTITY_ID: _CLIMATE, ATTR_TEMPERATURE: 25},
                blocking=True,
            )
        )
        release.set()
        await asyncio.gather(first, second)
    command = _last_command(mock_infrared_emitter_entity)
    assert command.model is expected_model
    assert (command.turbo, command.temperature) == (True, 25)


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
@pytest.mark.parametrize(
    ("extra_entry_data", "expected_model"),
    [
        (
            {CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY], CONF_MODEL: MODEL_YAP1F},
            GreeAcModel.YAP1F,
        ),
        (
            {
                CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
                CONF_MODEL: MODEL_GENERIC,
                CONF_GENERIC_OPTIONS: True,
            },
            GreeAcModel.GENERIC,
        ),
    ],
    indirect=["extra_entry_data"],
    ids=["yap1f", "generic-options"],
)
async def test_restore_switches_without_transmission(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    expected_model: GreeAcModel,
) -> None:
    """Restored options are visible on switches and used by the next send, not setup."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(_CLIMATE, HVACMode.OFF, {ATTR_TEMPERATURE: 24}),
                {
                    "last_active_hvac_mode": HVACMode.COOL.value,
                    "turbo": True,
                    "light": False,
                    "health": True,
                    "xfan": True,
                },
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_infrared_emitter_entity.send_command_calls == []
    assert [
        hass.states.get(_option_entity_id(hass, key)).state
        for key in ("turbo", "light", "health", "xfan")
    ] == ["on", "off", "on", "on"]
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    command = _last_command(mock_infrared_emitter_entity)
    assert command.model is expected_model
    assert (command.turbo, command.display, command.anion, command.blow) == (
        True,
        False,
        True,
        True,
    )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("extra_entry_data", "expected_model"),
    [
        (
            {CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY], CONF_MODEL: MODEL_YAP1F},
            GreeAcModel.YAP1F,
        ),
        (
            {
                CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
                CONF_MODEL: MODEL_GENERIC,
                CONF_GENERIC_OPTIONS: True,
            },
            GreeAcModel.GENERIC,
        ),
    ],
    indirect=["extra_entry_data"],
    ids=["yap1f", "generic-options"],
)
async def test_receiver_uses_selected_model_and_syncs_switches(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    expected_model: GreeAcModel,
) -> None:
    """Only the selected profile updates climate and canonical feature flags."""
    other_model = (
        GreeAcModel.GENERIC
        if expected_model is GreeAcModel.YAP1F
        else GreeAcModel.YAP1F
    )
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                model=other_model, mode=GreeAcMode.COOL, temperature=22
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()
    assert hass.states.get(_CLIMATE).state == HVACMode.OFF
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                model=expected_model,
                mode=GreeAcMode.COOL,
                temperature=25,
                turbo=True,
                display=False,
                anion=True,
                blow=True,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()
    assert hass.states.get(_CLIMATE).state == HVACMode.COOL
    assert hass.states.get(_CLIMATE).attributes[ATTR_TEMPERATURE] == 25
    assert [
        hass.states.get(_option_entity_id(hass, key)).state
        for key in ("turbo", "light", "health", "xfan")
    ] == ["on", "off", "on", "on"]
    assert mock_infrared_emitter_entity.send_command_calls == []


@pytest.mark.usefixtures("init_integration")
async def test_two_entries_keep_independent_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """One entry's option edit cannot leak into another entry's command."""

    second_emitter = MockInfraredEmitterEntity(
        "second_ir_emitter", name="Second IR emitter"
    )
    await hass.data[DATA_COMPONENT].async_add_entities([second_emitter])
    second = MockConfigEntry(
        domain=mock_config_entry.domain,
        title="Second Gree AC",
        data={
            CONF_INFRARED_EMITTER_ENTITY_ID: second_emitter.entity_id,
            CONF_MODEL: MODEL_YAP1F,
            CONF_HVAC_MODES: [HVACMode.COOL],
        },
    )
    second.add_to_hass(hass)
    await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: _option_entity_id(hass, "turbo")},
        blocking=True,
    )
    second_climate = hass.data[DOMAIN][second.entry_id].climate
    assert second_climate is not None
    await second_climate.async_set_hvac_mode(HVACMode.COOL)
    assert _last_command(second_emitter).turbo is False
    assert mock_infrared_emitter_entity.send_command_calls == []
    assert hass.data[DOMAIN][second.entry_id].turbo is False


@pytest.mark.usefixtures("init_integration")
async def test_option_switches_follow_emitter_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Switch availability follows emitter and unload leaves it unavailable."""
    light_entity_id = _option_entity_id(hass, "light")
    hass.states.async_set(EMITTER_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get(light_entity_id).state == STATE_UNAVAILABLE
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(light_entity_id).state == STATE_UNAVAILABLE
    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: light_entity_id}, blocking=True
    )
    assert mock_infrared_emitter_entity.send_command_calls == []
