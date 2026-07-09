"""Tests for the Habitron communicate (HbtnComm) layer (v2 thin transport)."""

from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import HabitronClient, HabitronTimeoutError, Module, Router
import pytest

from homeassistant.components.habitron.communicate import HbtnComm


def _make_comm(host: str = "192.168.1.50") -> HbtnComm:
    """Build an HbtnComm with the client stubbed out."""
    hass = MagicMock()
    hass.data = {"integrations": {"habitron": MagicMock(manifest={"version": "9.9.9"})}}
    hass.async_add_executor_job = AsyncMock()
    config = MagicMock()
    config.data = {"habitron_host": host}
    comm = HbtnComm(hass, config)
    comm._client = AsyncMock(spec=HabitronClient)
    return comm


# ---------------------------------------------------------------------------
# init / helpers / properties
# ---------------------------------------------------------------------------


def test_init_with_valid_ipv4_uses_host_directly() -> None:
    """A valid IPv4 in config is stored as the active host."""
    comm = _make_comm("10.0.0.5")
    assert comm._host == "10.0.0.5"


def test_init_with_hostname_leaves_host_empty() -> None:
    """A non-IPv4 hostname produces an empty initial host (resolved later)."""
    assert _make_comm("my-hub.local")._host == ""


def test_is_valid_ipv4() -> None:
    """``is_valid_ipv4`` accepts valid IPv4 only."""
    comm = _make_comm()
    assert comm.is_valid_ipv4("192.168.1.1") is True
    assert comm.is_valid_ipv4("not-an-ip") is False


def test_convert_mod_id_subtracts_hundred() -> None:
    """_convert_mod_id maps the bus address back to a raw module address."""
    comm = _make_comm()
    assert comm._convert_mod_id(105) == 5
    assert comm._convert_mod_id(100) == 0


def test_property_accessors() -> None:
    """Public properties expose the cached fields."""
    comm = _make_comm("10.0.0.5")
    comm._mac = "AA:BB"
    comm._version = "1.2.3"
    assert comm.com_ip == "10.0.0.5"
    assert comm.com_mac == "AA:BB"
    assert comm.com_version == "1.2.3"
    # Defaults until async_setup resolves it from the integration manifest.
    assert comm.hbtn_version == "0.0.0"


def test_router_property_returns_own_router() -> None:
    """``router`` returns the comm's own router, set via set_router."""
    comm = _make_comm()
    # Empty placeholder model until set_router stores the built one.
    assert isinstance(comm.router, Router)
    other = Router(uid="rt_y")
    comm.set_router(other)
    assert comm.router is other


def test_module_by_addr() -> None:
    """_module_by_addr finds a module by its full address."""
    comm = _make_comm()
    router = Router()
    mod = Module(uid="M", addr=105, typ=b"\x0a\x01", name="x")
    router.modules = [mod]
    comm.set_router(router)
    assert comm._module_by_addr(105) is mod
    assert comm._module_by_addr(999) is None


# ---------------------------------------------------------------------------
# command wrappers (transport pass-throughs)
# ---------------------------------------------------------------------------


async def test_set_output_converts_addr() -> None:
    """set_output converts the address and forwards a bool value."""
    comm = _make_comm()
    await comm.async_set_output(105, 2, 1)
    comm._client.set_output.assert_awaited_once_with(5, 2, True)


async def test_set_dimmval_and_flag() -> None:
    """Dim/flag setters forward converted addresses."""
    comm = _make_comm()
    await comm.async_set_dimmval(105, 1, 50)
    comm._client.set_dimmval.assert_awaited_once_with(5, 1, 50)
    await comm.async_set_flag(105, 3, 1)
    comm._client.set_flag.assert_awaited_once_with(5, 3, True)


async def test_set_analog_val_uses_dimm_channel_3() -> None:
    """The analogue output maps to dimm channel 3."""
    comm = _make_comm()
    await comm.async_set_analog_val(105, 1, 42)
    comm._client.set_dimmval.assert_awaited_once_with(5, 3, 42)


async def test_set_led_outp_offsets_by_output_count() -> None:
    """LED output number is offset by the module's output count."""
    comm = _make_comm()
    router = Router()
    mod = Module(uid="M", addr=105, typ=b"\x01\x02", name="x")
    mod.outputs = [object()] * 16  # 16 outputs
    router.modules = [mod]
    comm.set_router(router)
    await comm.async_set_led_outp(105, 0, 1)
    comm._client.set_output.assert_awaited_once_with(5, 16, True)


async def test_set_group_mode_and_climate() -> None:
    """Group-mode + climate setters pass through to the client."""
    comm = _make_comm()
    await comm.async_set_group_mode(2, 32)
    comm._client.set_group_mode.assert_awaited_once_with(2, 32)
    await comm.async_set_climate_mode(105, 1, 2)
    comm._client.set_climate_mode.assert_awaited_once_with(5, 1, 2)


# ---------------------------------------------------------------------------
# async_system_update -> async_refresh_system
# ---------------------------------------------------------------------------


async def test_async_system_update_suspended_returns_crc() -> None:
    """While suspended no refresh happens and the cached CRC is returned."""
    comm = _make_comm()
    comm.update_suspended = True
    comm.crc = 7
    with patch(
        "homeassistant.components.habitron.communicate.async_refresh_system",
        new=AsyncMock(),
    ) as refresh:
        assert await comm.async_system_update() == 7
        refresh.assert_not_called()


async def test_async_system_update_refreshes_and_returns_new_crc() -> None:
    """A normal tick refreshes the bus, returning the new CRC."""
    comm = _make_comm()
    with patch(
        "homeassistant.components.habitron.communicate.async_refresh_system",
        new=AsyncMock(return_value=99),
    ) as refresh:
        assert await comm.async_system_update() == 99
        refresh.assert_awaited()
        assert comm.crc == 99


# ---------------------------------------------------------------------------
# update_entity -> apply_event
# ---------------------------------------------------------------------------


async def test_update_entity_applies_event_when_host_matches() -> None:
    """A matching host forwards the event to ``apply_event``."""
    comm = _make_comm()
    comm._hostip = "1.2.3.4"
    router = Router()
    comm.set_router(router)
    with patch(
        "homeassistant.components.habitron.communicate.apply_event"
    ) as apply_evt:
        await comm.update_entity("1.2.3.4", 2, 1, 3, 1)
        apply_evt.assert_called_once_with(router, 2, 1, 3, 1, 0, 0, 0)


async def test_update_entity_ignores_foreign_host() -> None:
    """A non-matching host does not apply the event."""
    comm = _make_comm()
    comm._hostip = "1.2.3.4"
    with patch(
        "homeassistant.components.habitron.communicate.apply_event"
    ) as apply_evt:
        await comm.update_entity("9.9.9.9", 2, 1, 3, 1)
        apply_evt.assert_not_called()


# ---------------------------------------------------------------------------
# crc dedupe
# ---------------------------------------------------------------------------


async def test_get_compact_status_dedupes_on_unchanged_crc() -> None:
    """An unchanged CRC returns empty bytes (no work)."""
    comm = _make_comm()
    comm._stream_crc["compact"] = 42
    comm._client.get_compact_status = AsyncMock(return_value=(b"payload", 42))
    assert await comm.get_compact_status() == b""


async def test_get_compact_status_caches_new_crc() -> None:
    """A changed CRC returns the payload and caches the new CRC."""
    comm = _make_comm()
    comm._client.get_compact_status = AsyncMock(return_value=(b"payload", 7))
    assert await comm.get_compact_status() == b"payload"
    assert comm._stream_crc["compact"] == 7


# ---------------------------------------------------------------------------
# get_smhub_info
# ---------------------------------------------------------------------------


async def test_get_smhub_info_populates_fields() -> None:
    """get_smhub_info fills mac/version/host fields from the validated info."""
    comm = _make_comm()
    info = {
        "software": {"version": "1.0", "slug": "habitron"},
        "hardware": {
            "platform": {"type": "Raspberry Pi 4"},
            "network": {"ip": "10.0.0.5", "host": "smarthub", "lan mac": "AA:BB"},
        },
    }
    comm._client.get_smhub_info = AsyncMock(return_value=info)
    with patch(
        "homeassistant.components.habitron.communicate.os.getenv", return_value=None
    ):
        out = await comm.get_smhub_info()
    assert out["software"]["version"] == "1.0"
    assert comm.com_version == "1.0"
    assert comm.com_mac == "AA:BB"
    assert comm.com_ip == "10.0.0.5"


# ---------------------------------------------------------------------------
# async_setup
# ---------------------------------------------------------------------------


async def test_async_setup_resolves_host_and_connects() -> None:
    """async_setup resolves the host and connects a fresh client."""
    comm = _make_comm("my-hub.local")
    comm._client = None
    comm._hass.async_add_executor_job = AsyncMock(return_value="10.0.0.9")
    client = AsyncMock(spec=HabitronClient)
    with (
        patch(
            "homeassistant.components.habitron.communicate.network.async_get_source_ip",
            new=AsyncMock(return_value="10.0.0.1"),
        ),
        patch(
            "homeassistant.components.habitron.communicate.HabitronClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.habitron.communicate.async_get_integration",
            new=AsyncMock(return_value=MagicMock(version="3.0.2")),
        ),
    ):
        await comm.async_setup()
    assert comm._host == "10.0.0.9"
    assert comm.hbtn_version == "3.0.2"
    client.connect.assert_awaited()


# ---------------------------------------------------------------------------
# per-stream CRC dedup (firmware / module status)
# ---------------------------------------------------------------------------


async def test_get_module_status_dedupes_and_caches() -> None:
    """Module status returns the payload then dedupes on an unchanged CRC."""
    comm = _make_comm()
    comm._client.get_module_status = AsyncMock(return_value=(b"m", 5))
    assert await comm.get_module_status(105) == b"m"
    assert comm._stream_crc["modstat:105"] == 5
    assert await comm.get_module_status(105) == b""


async def test_handle_firmware_dedupes_and_caches() -> None:
    """Firmware status returns the payload then dedupes on an unchanged CRC."""
    comm = _make_comm()
    comm._client.handle_firmware = AsyncMock(return_value=(b"fw", 9))
    assert await comm.handle_firmware(5) == b"fw"
    assert comm._stream_crc["fw:5"] == 9
    assert await comm.handle_firmware(5) == b""


async def test_update_firmware_dedupes_and_caches() -> None:
    """Firmware update returns the payload then dedupes on an unchanged CRC."""
    comm = _make_comm()
    comm._client.update_firmware = AsyncMock(return_value=(b"u", 3))
    assert await comm.update_firmware(5) == b"u"
    assert comm._stream_crc["fwupd:5"] == 3
    assert await comm.update_firmware(5) == b""


async def test_stream_crcs_are_independent() -> None:
    """An identical CRC in a different stream does not dedupe (no clobber)."""
    comm = _make_comm()
    comm._client.get_compact_status = AsyncMock(return_value=(b"c", 7))
    comm._client.handle_firmware = AsyncMock(return_value=(b"f", 7))
    assert await comm.get_compact_status() == b"c"
    # Same CRC value, different stream → still returns its payload.
    assert await comm.handle_firmware(0) == b"f"
    assert comm._stream_crc["compact"] == 7
    assert comm._stream_crc["fw:0"] == 7
    # The bus-status stream keeps its own field untouched.
    assert comm.crc == 0


# ---------------------------------------------------------------------------
# command wrappers — module-addr converting pass-throughs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "args", "client_method", "expected"),
    [
        ("async_set_rgb_output", (105, 2, 1), "set_rgb_output", (5, 2, True)),
        ("async_set_rgbval", (105, 1, [1, 2, 3]), "set_rgbval", (5, 1, [1, 2, 3])),
        ("async_set_shutterpos", (105, 1, 40), "set_shutterpos", (5, 1, 40)),
        ("async_set_blindtilt", (105, 1, 30), "set_blindtilt", (5, 1, 30)),
        ("async_inc_dec_counter", (105, 2, 1), "inc_dec_counter", (5, 2, 1)),
        ("async_set_setpoint", (105, 1, 210), "set_setpoint", (5, 1, 210)),
        ("async_set_climate_mode", (105, 1, 2), "set_climate_mode", (5, 1, 2)),
        ("async_call_dir_command", (105, 7), "call_dir_command", (5, 7)),
        ("async_call_vis_command", (105, 7), "call_vis_command", (5, 7)),
        ("async_get_module_definitions", (105,), "get_module_definitions", (5,)),
        ("async_get_module_settings", (105,), "get_module_settings", (5,)),
        ("send_message", (105, 3), "send_message", (5, 3)),
        ("send_message_text", (105, "hi"), "send_message_text", (5, "hi")),
        ("send_sms", (105, 3, 9), "send_sms", (5, 3, 9)),
    ],
)
async def test_mod_id_converting_passthroughs(
    method: str, args: tuple, client_method: str, expected: tuple
) -> None:
    """Wrappers convert the bus address (105→5) and forward to the client."""
    comm = _make_comm()
    await getattr(comm, method)(*args)
    getattr(comm._client, client_method).assert_awaited_once_with(*expected)


# ---------------------------------------------------------------------------
# command wrappers — plain pass-throughs (no address conversion)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "args", "client_method", "expected"),
    [
        ("async_set_log_level", (1, 2), "set_log_level", (1, 2)),
        ("get_smr", (), "get_smr", ()),
        ("async_get_router_status", (), "get_router_status", ()),
        ("async_get_router_modules", (), "get_router_modules", ()),
        ("get_global_descriptions", (), "get_global_descriptions", ()),
        ("async_get_error_status", (), "get_error_status", ()),
        ("async_start_mirror", (), "start_mirror", ()),
        ("async_stop_mirror", (), "stop_mirror", ()),
        ("hub_restart", (), "hub_restart", ()),
        ("hub_reboot", (), "hub_reboot", ()),
        ("module_restart", (7,), "module_restart", (7,)),
        ("restart_fwd_tbl", (), "restart_fwd_tbl", ()),
        ("send_devregid", (5, "abc"), "send_devregid", (5, "abc")),
        ("async_call_coll_command", (7,), "call_coll_command", (7,)),
    ],
)
async def test_plain_passthroughs(
    method: str, args: tuple, client_method: str, expected: tuple
) -> None:
    """Wrappers without address conversion forward verbatim to the client."""
    comm = _make_comm()
    await getattr(comm, method)(*args)
    getattr(comm._client, client_method).assert_awaited_once_with(*expected)


# ---------------------------------------------------------------------------
# mode-setting helpers with mapping logic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("new_mode", "expected"), [(1, 0x42), (2, 0x43)])
async def test_set_daytime_mode_maps_to_group_mode(
    new_mode: int, expected: int
) -> None:
    """Daytime modes 1/2 map to group-mode 0x42/0x43."""
    comm = _make_comm()
    await comm.async_set_daytime_mode(2, new_mode)
    comm._client.set_group_mode.assert_awaited_once_with(2, expected)


async def test_set_daytime_mode_ignores_unknown_value() -> None:
    """An unmapped daytime value sends nothing."""
    comm = _make_comm()
    await comm.async_set_daytime_mode(2, 3)
    comm._client.set_group_mode.assert_not_called()


@pytest.mark.parametrize(("alarm", "expected"), [(True, 0x40), (False, 0x41)])
async def test_set_alarm_mode_maps_to_group_mode(alarm: bool, expected: int) -> None:
    """Alarm on/off maps to group-mode 0x40/0x41."""
    comm = _make_comm()
    await comm.async_set_alarm_mode(2, alarm)
    comm._client.set_group_mode.assert_awaited_once_with(2, expected)


async def test_power_cycle_channel_downs_then_ups_with_pause() -> None:
    """Power-cycle downs the channel, waits, then ups it again."""
    comm = _make_comm()
    with patch(
        "homeassistant.components.habitron.communicate.asyncio.sleep",
        new=AsyncMock(),
    ) as mock_sleep:
        await comm.async_power_cycle_channel(2)
    comm._client.power_cycle_channel_down.assert_awaited_once_with(2)
    comm._client.power_cycle_channel_up.assert_awaited_once_with(2)
    mock_sleep.assert_awaited_once_with(2)


# ---------------------------------------------------------------------------
# config-file save helpers
# ---------------------------------------------------------------------------


async def test_save_module_status_uses_module_filename() -> None:
    """save_module_status reads the module status and writes a .mstat file."""
    comm = _make_comm()
    comm.get_module_status = AsyncMock(return_value=b"\x01\x02\x03")
    comm.save_config_data = AsyncMock()
    await comm.save_module_status(105)
    assert comm.save_config_data.call_args.args[0] == "Module_105.mstat"


async def test_save_router_status_uses_router_filename() -> None:
    """save_router_status reads the router status and writes a .rstat file."""
    comm = _make_comm()
    comm.async_get_router_status = AsyncMock(return_value=b"\x01\x02")
    comm.save_config_data = AsyncMock()
    await comm.save_router_status()
    assert comm.save_config_data.call_args.args[0] == "Router_1.rstat"


async def test_save_smg_file_serialises_bytes() -> None:
    """save_smg_file renders settings bytes as semicolon-separated values."""
    comm = _make_comm()
    comm.async_get_module_settings = AsyncMock(return_value=b"\x01\x02")
    comm.save_config_data = AsyncMock()
    await comm.save_smg_file(105)
    fname, data = comm.save_config_data.call_args.args
    assert fname == "Module_105.smg"
    assert data == "1;2;"


async def test_save_smr_file_serialises_bytes() -> None:
    """save_smr_file renders router-settings bytes as semicolon-separated values."""
    comm = _make_comm()
    comm.get_smr = AsyncMock(return_value=b"\x05")
    comm.save_config_data = AsyncMock()
    await comm.save_smr_file()
    fname, data = comm.save_config_data.call_args.args
    assert fname == "Router_1.smr"
    assert data == "5;"


async def test_save_smc_file_writes_library_formatted_text() -> None:
    """save_smc_file writes the .smc text the library formats from the module."""
    comm = _make_comm()
    comm._client.get_module_definitions_smc = AsyncMock(return_value="0;1;2;\r")
    comm.save_config_data = AsyncMock()
    await comm.save_smc_file(105)
    # mod_id 105 -> bus address 5; filename keeps the mod_id.
    comm._client.get_module_definitions_smc.assert_awaited_once_with(5)
    assert comm.save_config_data.call_args.args == ("Module_105.smc", "0;1;2;\r")


async def test_save_config_data_writes_via_anyio() -> None:
    """save_config_data ensures the dir then writes the payload to the file."""
    comm = _make_comm()
    comm._hass.async_add_executor_job = AsyncMock()
    mock_file = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_file)
    ctx.__aexit__ = AsyncMock(return_value=False)
    with patch(
        "homeassistant.components.habitron.communicate.anyio.open_file",
        new=AsyncMock(return_value=ctx),
    ):
        await comm.save_config_data("Dump.txt", "payload;")
    comm._hass.async_add_executor_job.assert_awaited()  # mkdir
    mock_file.write.assert_awaited_once_with("payload;")


# ---------------------------------------------------------------------------
# connection guard / host resolution / reconfigure / info errors
# ---------------------------------------------------------------------------


def test_client_property_raises_when_not_connected() -> None:
    """Accessing ``client`` before async_setup is a hard error."""
    comm = _make_comm()
    comm._client = None
    with pytest.raises(RuntimeError, match="not connected"):
        _ = comm.client


async def test_async_setup_local_host_uses_own_ip() -> None:
    """A ``local`` host resolves via get_own_ip (the add-on/same-host path)."""
    comm = _make_comm("local")
    comm._client = None
    comm._hass.async_add_executor_job = AsyncMock(return_value="10.0.0.9")
    client = AsyncMock(spec=HabitronClient)
    with (
        patch(
            "homeassistant.components.habitron.communicate.network.async_get_source_ip",
            new=AsyncMock(return_value="10.0.0.1"),
        ),
        patch(
            "homeassistant.components.habitron.communicate.HabitronClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.habitron.communicate.async_get_integration",
            new=AsyncMock(return_value=MagicMock(version="3.0.2")),
        ),
    ):
        await comm.async_setup()
    assert comm._host == "10.0.0.9"
    assert comm.hbtn_version == "3.0.2"
    client.connect.assert_awaited()


async def test_get_smhub_info_timeout_reraises() -> None:
    """A timeout during the info fetch is re-raised as HabitronTimeoutError."""
    comm = _make_comm()
    comm._client.get_smhub_info = AsyncMock(side_effect=HabitronTimeoutError("t"))
    with pytest.raises(HabitronTimeoutError):
        await comm.get_smhub_info()


async def test_get_smhub_info_generic_error_reraises() -> None:
    """An unexpected error during the info fetch propagates unchanged."""
    comm = _make_comm()
    comm._client.get_smhub_info = AsyncMock(side_effect=ValueError("boom"))
    with pytest.raises(ValueError, match="boom"):
        await comm.get_smhub_info()


async def test_set_led_outp_unknown_module_is_noop() -> None:
    """async_set_led_outp on an unknown module logs and sends nothing."""
    comm = _make_comm()
    comm.set_router(Router())  # no modules
    await comm.async_set_led_outp(999, 0, 1)
    comm._client.set_output.assert_not_called()


def test_hostname_property_returns_cached_value() -> None:
    """The hostname property exposes the cached hub hostname."""
    comm = _make_comm()
    comm._hostname = "smarthub-1"
    assert comm.hostname == "smarthub-1"


async def test_get_smhub_version_passthrough() -> None:
    """get_smhub_version forwards to the client unchanged."""
    comm = _make_comm()
    comm._client.get_smhub_version = AsyncMock(return_value=b"SmartIP 1.2.3")
    assert await comm.get_smhub_version() == b"SmartIP 1.2.3"
