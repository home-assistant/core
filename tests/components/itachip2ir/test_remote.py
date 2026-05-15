"""Tests for iTach IP2IR remote platform."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.itachip2ir.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DOMAIN,
)
from homeassistant.components.itachip2ir.remote import (
    InfraredRemoteEntity,
    _parse_remote_command,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo

HOST = "192.168.1.211"
DEVICE_ID = "GlobalCache_000C1E123456"


def _infrared_entity_id(port: int = 1) -> str:
    """Return a test infrared entity id."""
    return f"infrared.port_{port}"


def _entity(
    commands: dict[str, str] | None = None,
    *,
    infrared_entity_id: str = "infrared.port_1",
) -> InfraredRemoteEntity:
    """Create a virtual remote entity."""
    return InfraredRemoteEntity(
        remote_id="living_room_tv",
        name="Living Room TV",
        infrared_entity_id=infrared_entity_id,
        commands=commands,
        unique_id_prefix=DEVICE_ID,
        device_info=DeviceInfo(
            identifiers={(DOMAIN, DEVICE_ID)},
            name=f"iTach IP2IR ({HOST})",
            manufacturer="Global Caché",
            model="iTach IP2IR",
            configuration_url=f"http://{HOST}",
        ),
    )


def test_remote_entity_properties() -> None:
    """Test virtual remote entity properties."""
    entity = _entity({"power_on": "100,200"})

    assert entity.name == "Living Room TV"
    assert entity.unique_id == f"{DEVICE_ID}_remote_living_room_tv"
    assert entity.is_on is True
    assert entity.available is True


def test_remote_device_info() -> None:
    """Test virtual remote device info."""
    entity = _entity()

    assert entity.device_info == {
        "identifiers": {(DOMAIN, DEVICE_ID)},
        "name": f"iTach IP2IR ({HOST})",
        "manufacturer": "Global Caché",
        "model": "iTach IP2IR",
        "configuration_url": f"http://{HOST}",
    }


@pytest.mark.asyncio
async def test_async_setup_entry_adds_configured_virtual_remotes() -> None:
    """Test setup creates remotes from configured options."""
    entry = SimpleNamespace(
        runtime_data=SimpleNamespace(
            host=HOST,
            device_id=DEVICE_ID,
            ir_enabled_ports=[1, 3],
        ),
        options={
            CONF_VIRTUAL_REMOTES: [
                {
                    CONF_REMOTE_ID: "living_room_tv",
                    CONF_REMOTE_NAME: "Living Room TV",
                    CONF_INFRARED_ENTITY_ID: _infrared_entity_id(1),
                    CONF_REMOTE_COMMANDS: {"power_on": "100,200"},
                },
                {
                    CONF_REMOTE_ID: "main_amplifier",
                    CONF_REMOTE_NAME: "Main Amplifier",
                    CONF_INFRARED_ENTITY_ID: _infrared_entity_id(3),
                    CONF_REMOTE_COMMANDS: {"power_on": "300,400"},
                },
            ]
        },
    )
    added: list[InfraredRemoteEntity] = []

    add_entities = MagicMock(
        side_effect=lambda entities, update_before_add=False: added.extend(entities)
    )

    await async_setup_entry(MagicMock(), cast(ConfigEntry, entry), add_entities)

    assert len(added) == 2
    assert added[0].name == "Living Room TV"
    assert added[0].unique_id == f"{DEVICE_ID}_remote_living_room_tv"
    assert added[1].name == "Main Amplifier"
    assert added[1].unique_id == f"{DEVICE_ID}_remote_main_amplifier"
    add_entities.assert_called_once()


@pytest.mark.asyncio
async def test_async_setup_entry_reads_virtual_remotes_from_data() -> None:
    """Test setup can create remotes from config entry data fallback."""
    entry = SimpleNamespace(
        runtime_data=SimpleNamespace(
            host=HOST,
            device_id=DEVICE_ID,
            ir_enabled_ports=[1],
        ),
        options={},
        data={
            CONF_VIRTUAL_REMOTES: [
                {
                    CONF_REMOTE_ID: "living_room_tv",
                    CONF_REMOTE_NAME: "Living Room TV",
                    CONF_INFRARED_ENTITY_ID: _infrared_entity_id(1),
                    CONF_REMOTE_COMMANDS: {"power_on": "100,200"},
                }
            ]
        },
    )
    added: list[InfraredRemoteEntity] = []

    add_entities = MagicMock(
        side_effect=lambda entities, update_before_add=False: added.extend(entities)
    )

    await async_setup_entry(MagicMock(), cast(ConfigEntry, entry), add_entities)

    assert len(added) == 1
    assert added[0].name == "Living Room TV"
    assert added[0].unique_id == f"{DEVICE_ID}_remote_living_room_tv"


@pytest.mark.asyncio
async def test_async_setup_entry_adds_only_valid_enabled_virtual_remotes() -> None:
    """Test setup creates remotes from valid options and skips invalid entries."""
    entry = SimpleNamespace(
        runtime_data=SimpleNamespace(
            host=HOST,
            device_id=DEVICE_ID,
            ir_enabled_ports=[1, 3],
        ),
        options={
            CONF_VIRTUAL_REMOTES: [
                {
                    CONF_REMOTE_ID: "living_room_tv",
                    CONF_REMOTE_NAME: "Living Room TV",
                    CONF_INFRARED_ENTITY_ID: _infrared_entity_id(1),
                    CONF_REMOTE_COMMANDS: {"power_on": "100,200"},
                },
                {
                    CONF_REMOTE_ID: "bad_remote",
                    CONF_REMOTE_NAME: "Bad Remote",
                },
            ]
        },
    )
    added: list[InfraredRemoteEntity] = []

    add_entities = MagicMock(
        side_effect=lambda entities, update_before_add=False: added.extend(entities)
    )

    await async_setup_entry(MagicMock(), cast(ConfigEntry, entry), add_entities)

    assert len(added) == 1
    assert added[0].name == "Living Room TV"
    assert added[0].unique_id == f"{DEVICE_ID}_remote_living_room_tv"


@pytest.mark.asyncio
async def test_remote_turn_on_and_off_with_configured_commands() -> None:
    """Test virtual remote can send configured on/off commands."""
    entity = _entity({"power_on": "100,200", "power_off": "300,400"})

    with (
        patch.object(entity, "async_write_ha_state") as write_state,
        patch.object(entity, "_async_send_named_command", AsyncMock()) as send,
    ):
        await entity.async_turn_off()
        await entity.async_turn_on()

    assert send.await_args_list[0].args[0] == "power_off"
    assert send.await_args_list[1].args[0] == "power_on"
    assert entity.is_on is True
    assert write_state.call_count == 2


@pytest.mark.asyncio
async def test_remote_turn_on_off_without_commands_leave_state_unchanged() -> None:
    """Test turn on/off do not mutate state without configured commands."""
    entity = _entity()

    with patch.object(entity, "async_write_ha_state") as write_state:
        await entity.async_turn_off()
        assert entity.is_on is True

        await entity.async_turn_on()
        assert entity.is_on is True

    write_state.assert_not_called()


@pytest.mark.asyncio
async def test_remote_toggle_uses_configured_toggle_command() -> None:
    """Test toggle command sends configured command and toggles state."""
    entity = _entity({"toggle": "100,200"})

    with (
        patch.object(entity, "async_write_ha_state") as write_state,
        patch.object(entity, "_async_send_named_command", AsyncMock()) as send,
    ):
        await entity.async_toggle()

    send.assert_awaited_once()
    assert send.await_args is not None
    assert send.await_args.args[0] == "toggle"
    assert entity.is_on is False
    write_state.assert_called_once()


@pytest.mark.asyncio
async def test_remote_toggle_falls_back_to_power_toggle() -> None:
    """Test toggle falls back to power_toggle command."""
    entity = _entity({"power_toggle": "100,200"})

    with (
        patch.object(entity, "async_write_ha_state"),
        patch.object(entity, "_async_send_named_command", AsyncMock()) as send,
    ):
        await entity.async_toggle()

    assert send.await_args is not None
    assert send.await_args.args[0] == "power_toggle"


@pytest.mark.asyncio
async def test_remote_toggle_without_command_leaves_state_unchanged() -> None:
    """Test toggle does not mutate state without a configured command."""
    entity = _entity()

    with patch.object(entity, "async_write_ha_state") as write_state:
        await entity.async_toggle()

    assert entity.is_on is True
    write_state.assert_not_called()


@pytest.mark.asyncio
async def test_remote_send_command_rejects_invalid_repeats() -> None:
    """Test remote send_command rejects invalid num_repeats."""
    entity = _entity()

    with pytest.raises(HomeAssistantError):
        await entity.async_send_command("100,200", num_repeats=-1)


@pytest.mark.asyncio
async def test_remote_send_command_resolves_named_command(hass: HomeAssistant) -> None:
    """Test send_command resolves configured named commands."""
    entity = _entity({"volume_up": "100,200"})
    entity.hass = hass

    with (
        patch.object(
            entity,
            "_resolve_infrared_entity_id",
            return_value="infrared.port_1",
        ),
        patch(
            "homeassistant.components.itachip2ir.remote.infrared.async_send_command",
            AsyncMock(),
        ) as send,
    ):
        await entity.async_send_command("volume_up")

    send.assert_awaited_once()
    assert send.await_args is not None
    ir_command = send.await_args.args[2]
    assert ir_command.modulation == 38_000
    assert [(item.high_us, item.low_us) for item in ir_command.get_raw_timings()] == [
        (100, 200)
    ]


@pytest.mark.asyncio
async def test_remote_send_command_accepts_raw_command(hass: HomeAssistant) -> None:
    """Test send_command accepts raw timing payloads."""
    entity = _entity()
    entity.hass = hass

    with (
        patch.object(
            entity,
            "_resolve_infrared_entity_id",
            return_value="infrared.port_1",
        ),
        patch(
            "homeassistant.components.itachip2ir.remote.infrared.async_send_command",
            AsyncMock(),
        ) as send,
    ):
        await entity.async_send_command("40000:100,200")

    send.assert_awaited_once()
    assert send.await_args is not None
    ir_command = send.await_args.args[2]
    assert ir_command.modulation == 40_000


@pytest.mark.asyncio
async def test_remote_send_command_repeats_and_delays(hass: HomeAssistant) -> None:
    """Test send_command supports repeated raw commands with delay."""
    entity = _entity()
    entity.hass = hass

    with (
        patch.object(
            entity,
            "_resolve_infrared_entity_id",
            return_value="infrared.port_1",
        ),
        patch(
            "homeassistant.components.itachip2ir.remote.infrared.async_send_command",
            AsyncMock(),
        ) as send,
        patch(
            "homeassistant.components.itachip2ir.remote.asyncio.sleep",
            AsyncMock(),
        ) as sleep,
    ):
        await entity.async_send_command(
            ["100,200", "300,400"],
            num_repeats=2,
            delay_secs=0.1,
        )

    assert send.await_count == 4
    assert sleep.await_count == 3


@pytest.mark.asyncio
async def test_remote_send_command_reraises_home_assistant_error(
    hass: HomeAssistant,
) -> None:
    """Test HomeAssistantError from infrared helper is not wrapped."""
    entity = _entity()
    entity.hass = hass

    with (
        patch.object(
            entity,
            "_resolve_infrared_entity_id",
            return_value="infrared.port_1",
        ),
        patch(
            "homeassistant.components.itachip2ir.remote.infrared.async_send_command",
            AsyncMock(side_effect=HomeAssistantError("boom")),
        ),
        pytest.raises(HomeAssistantError, match="boom"),
    ):
        await entity.async_send_command("100,200")


@pytest.mark.asyncio
async def test_remote_send_command_wraps_unexpected_error(hass: HomeAssistant) -> None:
    """Test unexpected infrared send errors are wrapped."""
    entity = _entity()
    entity.hass = hass

    with (
        patch.object(
            entity,
            "_resolve_infrared_entity_id",
            return_value="infrared.port_1",
        ),
        patch(
            "homeassistant.components.itachip2ir.remote.infrared.async_send_command",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await entity.async_send_command("100,200")


def test_parse_json_command_with_modulation() -> None:
    """Test JSON command parsing with modulation."""
    command = _parse_remote_command(
        '{"modulation": 40000, "timings": [100, 200]}',
        {},
    )

    assert command.modulation == 40_000
    assert [(item.high_us, item.low_us) for item in command.get_raw_timings()] == [
        (100, 200)
    ]


def test_parse_json_command_with_carrier_frequency_default() -> None:
    """Test JSON command parsing with carrier_frequency."""
    command = _parse_remote_command(
        '{"carrier_frequency": 36000, "timings": [100, 200]}',
        {},
    )

    assert command.modulation == 36_000


def test_parse_json_command_uses_default_modulation() -> None:
    """Test JSON command parsing defaults modulation."""
    command = _parse_remote_command('{"timings": [100, 200]}', {})

    assert command.modulation == 38_000


@pytest.mark.parametrize(
    "payload",
    [
        "{bad json",
        "[]",
        '{"modulation": "bad", "timings": [100, 200]}',
        '{"modulation": 38000, "timings": "100,200"}',
        '{"modulation": 38000, "timings": [100, "", 200, 300]}',
    ],
)
def test_parse_json_command_rejects_invalid_payloads(payload: str) -> None:
    """Test invalid JSON command payloads raise HomeAssistantError."""
    with pytest.raises(HomeAssistantError):
        _parse_remote_command(payload, {})


def test_parse_text_command_with_modulation_prefix() -> None:
    """Test text timing command with modulation prefix."""
    command = _parse_remote_command("40000:100,200,300,400", {})

    assert command.modulation == 40_000
    assert [(item.high_us, item.low_us) for item in command.get_raw_timings()] == [
        (100, 200),
        (300, 400),
    ]


def test_parse_text_command_with_kwargs_modulation() -> None:
    """Test text timing command uses modulation from kwargs."""
    command = _parse_remote_command("100,200", {"modulation": 56_000})

    assert command.modulation == 56_000


def test_parse_text_command_with_kwargs_carrier_frequency() -> None:
    """Test text timing command uses carrier_frequency from kwargs."""
    command = _parse_remote_command("100,200", {"carrier_frequency": 36_000})

    assert command.modulation == 36_000


@pytest.mark.parametrize(
    "kwargs",
    [
        {"modulation": "bad"},
        {"carrier_frequency": "bad"},
    ],
)
def test_parse_text_command_rejects_invalid_default_modulation(
    kwargs: dict[str, str],
) -> None:
    """Test invalid modulation kwargs raise HomeAssistantError."""
    with pytest.raises(HomeAssistantError):
        _parse_remote_command("100,200", kwargs)


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "bad:100,200",
        "100",
        "100,0",
        "100,-1",
        "100,,200",
        "100, ,200",
    ],
)
def test_parse_text_command_rejects_invalid_payloads(payload: str) -> None:
    """Test invalid text timing payloads raise HomeAssistantError."""
    with pytest.raises(HomeAssistantError):
        _parse_remote_command(payload, {})


def test_parse_pronto_command() -> None:
    """Test raw learned Pronto command parsing."""
    command = _parse_remote_command("0000 006D 0001 0000 0010 0020", {})

    assert command.modulation > 0
    assert [(item.high_us, item.low_us) for item in command.get_raw_timings()]


@pytest.mark.parametrize(
    "payload",
    [
        "0000 006D 0000",
        "0100 006D 0001 0000 0010 0020",
        "0000 0000 0001 0000 0010 0020",
        "0000 006D 0002 0000 0010 0020",
    ],
)
def test_parse_pronto_command_rejects_invalid_payloads(payload: str) -> None:
    """Test invalid Pronto payloads raise HomeAssistantError."""
    with pytest.raises(HomeAssistantError):
        _parse_remote_command(payload, {})


@pytest.mark.asyncio
async def test_async_setup_entry_skips_malformed_command_mapping() -> None:
    """Test setup skips malformed remotes with non-mapping commands."""
    entry = SimpleNamespace(
        runtime_data=SimpleNamespace(
            host=HOST,
            device_id=DEVICE_ID,
            ir_enabled_ports=[1],
        ),
        options={
            CONF_VIRTUAL_REMOTES: [
                {
                    CONF_REMOTE_ID: "bad",
                    CONF_REMOTE_NAME: "Bad",
                    CONF_INFRARED_ENTITY_ID: _infrared_entity_id(1),
                    CONF_REMOTE_COMMANDS: object(),
                }
            ]
        },
    )
    added: list[InfraredRemoteEntity] = []
    add_entities = MagicMock(
        side_effect=lambda entities, update_before_add=False: added.extend(entities)
    )

    await async_setup_entry(MagicMock(), cast(ConfigEntry, entry), add_entities)

    assert added == []


def test_remote_unavailable_when_infrared_entity_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test remote availability follows the paired infrared entity state."""
    entity = _entity(infrared_entity_id="infrared.port_1")
    entity.hass = hass
    hass.states.async_set("infrared.port_1", "unavailable")

    assert entity.available is False


def test_resolve_infrared_entity_id_returns_configured_entity() -> None:
    """Test configured infrared entity ids are returned directly."""
    entity = _entity(infrared_entity_id="infrared.direct")

    assert entity._resolve_infrared_entity_id() == "infrared.direct"


@pytest.mark.asyncio
async def test_remote_send_command_rejects_invalid_delay_values() -> None:
    """Test remote send_command rejects invalid delay values."""
    entity = _entity()

    with pytest.raises(HomeAssistantError):
        await entity.async_send_command("100,200", delay_secs="bad")

    with pytest.raises(HomeAssistantError):
        await entity.async_send_command("100,200", delay_secs=-0.1)


@pytest.mark.asyncio
async def test_remote_send_command_rejects_non_integer_repeats() -> None:
    """Test remote send_command rejects non-integer repeat counts."""
    entity = _entity()

    with pytest.raises(HomeAssistantError):
        await entity.async_send_command("100,200", num_repeats="bad")


def test_remote_unavailable_when_infrared_entity_state_missing(
    hass: HomeAssistant,
) -> None:
    """Test remote is unavailable when the associated infrared entity is missing."""
    entity = _entity(infrared_entity_id="infrared.missing")
    entity.hass = hass

    assert entity.available is False


@pytest.mark.asyncio
async def test_remote_send_without_hass_raises_missing_infrared_error() -> None:
    """Test sending before the entity is attached raises a translated error."""
    entity = _entity()

    with pytest.raises(HomeAssistantError) as exc:
        await entity.async_send_command("100,200")

    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "remote_infrared_missing"
    assert exc.value.translation_placeholders == {"entity_id": "infrared.port_1"}


@pytest.mark.asyncio
async def test_remote_send_command_rejects_zero_repeats() -> None:
    """Test remote send_command rejects zero repeat counts before sending."""
    entity = _entity()

    with pytest.raises(HomeAssistantError) as exc:
        await entity.async_send_command("100,200", num_repeats=0)

    assert exc.value.translation_key == "remote_invalid_service_parameter"
    assert exc.value.translation_placeholders is not None
    assert "num_repeats" in exc.value.translation_placeholders["error"]
