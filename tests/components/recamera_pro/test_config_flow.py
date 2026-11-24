"""Config flow and options flow tests for reCamera Pro."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from recamera_protocol import (
    RecameraAuthenticationError,
    RecameraConnectionError,
    RecameraDeviceInfo,
    RecameraError,
    RecameraProbeResult,
    RecameraProtocolError,
)
from zeroconf import NotRunningException

from homeassistant import data_entry_flow
from homeassistant.components.recamera_pro.config_flow import (
    RecameraProConfigFlow,
    RecameraProOptionsFlow,
    _any_host_reachable,
    _async_probe_device_with_hass,
    _async_resolve_zeroconf_service,
    _is_ignored_discovery_host,
    _options_catalog,
    _prioritize_reachable_hosts,
    _text,
)
from homeassistant.components.recamera_pro.const import (
    CONF_AUDIO_CONFIDENCE,
    CONF_AUDIO_COOLDOWN,
    CONF_CLASS_STALE_SECONDS,
    CONF_DEVICE_ID,
    CONF_LANGUAGE,
    CONF_MAC_ADDRESS,
    CONF_SERIAL_NUMBER,
    CONF_TRACKED_CLASSES,
    CONF_VISUAL_CONFIDENCE,
    CONF_VISUAL_CONFIRM,
    CONF_VISUAL_COOLDOWN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType


def _probe(
    *,
    mac: str = "4a:f8:34:07:ab:3d",
    serial: str | None = "SN123456",
    fw: str = "V1.3.0",
) -> RecameraProbeResult:
    return RecameraProbeResult(
        info=RecameraDeviceInfo(
            mac_address=mac,
            serial_number=serial,
            base_plate_model="reCamera Pro",
            firmware_version=fw,
        ),
        capabilities={},
    )


def _make_flow() -> RecameraProConfigFlow:
    flow = RecameraProConfigFlow()
    flow.hass = SimpleNamespace(
        data={},
        config_entries=SimpleNamespace(
            async_update_entry=Mock(),
            async_reload=AsyncMock(),
            flow=SimpleNamespace(async_progress_by_handler=lambda _d: []),
        ),
    )
    flow.context = {}
    flow._async_current_entries = list
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock()
    flow._async_abort_entries_match = Mock()
    flow.async_create_entry = Mock(
        side_effect=lambda **kw: {"type": FlowResultType.CREATE_ENTRY, **kw}
    )
    flow.async_show_form = Mock(
        side_effect=lambda **kw: {"type": FlowResultType.FORM, **kw}
    )
    flow.async_abort = Mock(
        side_effect=lambda **kw: {"type": FlowResultType.ABORT, **kw}
    )
    return flow


@pytest.mark.asyncio
async def test_user_flow_success_and_errors() -> None:
    """Test manual user setup success, auth failure, and connection failure."""
    flow = _make_flow()
    flow.hass.config_entries.async_schedule_reload = Mock()
    form = await flow.async_step_user()
    assert form["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(side_effect=RecameraConnectionError("offline")),
    ):
        res = await flow.async_step_user(
            {CONF_HOST: "192.168.10.250", CONF_USERNAME: "admin", CONF_PASSWORD: "p"}
        )
    assert res["errors"]["base"] == "cannot_connect"

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(side_effect=RecameraAuthenticationError("bad")),
    ):
        res = await flow.async_step_user(
            {CONF_HOST: "192.168.10.22", CONF_USERNAME: "admin", CONF_PASSWORD: "bad"}
        )
    assert res["errors"]["base"] == "invalid_auth"

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe()),
    ):
        res = await flow.async_step_user(
            {
                CONF_HOST: "192.168.10.22",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "recamera.1",
            }
        )
    assert res["type"] == FlowResultType.CREATE_ENTRY
    assert res["data"][CONF_HOST] == "192.168.10.22"
    assert res["data"][CONF_SERIAL_NUMBER] == "SN123456"


@pytest.mark.asyncio
async def test_zeroconf_filters_bridge_and_other_entry_hosts() -> None:
    """Test Zeroconf discovery skips bridge IPs and IPs owned by other entries."""
    flow = _make_flow()
    flow.hass.config_entries.async_schedule_reload = Mock()
    other_entry = SimpleNamespace(
        entry_id="e1",
        unique_id="4a:f8:34:07:ab:3d",
        data={CONF_HOST: "192.168.10.22", CONF_DEVICE_ID: "4a:f8:34:07:ab:3d"},
    )
    flow._async_current_entries = lambda: [other_entry]
    flow._start_discovery_refresh = Mock()

    discovery_info = SimpleNamespace(
        type="_recamera._tcp.local.",
        name="reCamera Pro (FE:47:BC:57:26:0A)._recamera._tcp.local.",
        host="172.30.32.1",
        ip_addresses=["172.30.32.1", "192.168.10.22", "192.168.7.214"],
        properties={"mac": "fe:47:bc:57:26:0a", "id": "FE47BC57260A"},
    )
    with patch(
        "homeassistant.components.recamera_pro.config_flow._prioritize_reachable_hosts",
        new=AsyncMock(side_effect=list),
    ):
        res = await flow.async_step_zeroconf(discovery_info)
    assert res["type"] == FlowResultType.FORM
    assert flow._discovery_host == "192.168.7.214"


@pytest.mark.asyncio
async def test_zeroconf_confirm_does_not_trust_unverified_mdns_serial() -> None:
    """Test mDNS serial is not written to entry data unless verified by HTTP probe."""
    flow = _make_flow()
    flow.hass.config_entries.async_schedule_reload = Mock()
    flow._discovery_mac = "fe:47:bc:57:26:0a"
    flow._discovery_serial = "UNVERIFIED_MDNS_SERIAL"
    flow._discovery_host = "192.168.7.214"
    flow._discovery_hosts = ["192.168.7.214"]
    flow._cancel_discovery_refresh = Mock()

    probe_no_serial = _probe(mac="fe:47:bc:57:26:0a", serial=None)
    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=probe_no_serial),
    ):
        res = await flow.async_step_zeroconf_confirm(
            {
                CONF_HOST: "192.168.7.214",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "recamera.1",
            }
        )
    assert res["type"] == FlowResultType.CREATE_ENTRY
    assert flow.async_set_unique_id.call_args.args[0] == "fe:47:bc:57:26:0a"
    assert getattr(flow, "unique_id", None) is None
    assert res["data"].get(CONF_SERIAL_NUMBER) is None


@pytest.mark.asyncio
async def test_reconfigure_and_reauth_flows() -> None:
    """Test reconfigure keeping password blank and reauth updating password."""
    entry = SimpleNamespace(
        entry_id="e1",
        unique_id="SN123456",
        data={
            CONF_HOST: "192.168.10.22",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "old_password",
            CONF_MAC_ADDRESS: "4a:f8:34:07:ab:3d",
            CONF_SERIAL_NUMBER: "SN123456",
        },
    )
    flow = _make_flow()
    flow.hass.config_entries.async_schedule_reload = Mock()
    flow._get_reconfigure_entry = lambda: entry
    flow.async_update_reload_and_abort = Mock(
        return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
    )

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe()),
    ) as probe_mock:
        res = await flow.async_step_reconfigure(
            {CONF_HOST: "192.168.10.22", CONF_USERNAME: "admin", CONF_PASSWORD: ""}
        )
    assert res["reason"] == "reconfigure_successful"
    assert probe_mock.await_args.args[3] == "old_password"

    flow2 = _make_flow()
    flow2._get_reauth_entry = lambda: entry
    flow2.async_update_reload_and_abort = Mock(
        return_value={"type": FlowResultType.ABORT, "reason": "reauth_successful"}
    )
    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(side_effect=RecameraAuthenticationError("bad")),
    ):
        res_err = await flow2.async_step_reauth_confirm(
            {CONF_USERNAME: "admin", CONF_PASSWORD: "wrong"}
        )
    assert res_err["errors"]["base"] == "invalid_auth"

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe()),
    ):
        res_ok = await flow2.async_step_reauth_confirm(
            {CONF_USERNAME: "admin", CONF_PASSWORD: "new_password"}
        )
    assert res_ok["reason"] == "reauth_successful"


@pytest.mark.asyncio
async def test_options_flow_steps() -> None:
    """Test options flow vision, sound, classes, and compatibility steps."""
    entry = SimpleNamespace(
        entry_id="e1",
        options={
            CONF_VISUAL_CONFIDENCE: 0.5,
            CONF_VISUAL_CONFIRM: 0.0,
            CONF_CLASS_STALE_SECONDS: 8.0,
            CONF_VISUAL_COOLDOWN: 2.0,
            CONF_AUDIO_CONFIDENCE: 0.8,
            CONF_AUDIO_COOLDOWN: 5.0,
            CONF_TRACKED_CLASSES: [],
            CONF_LANGUAGE: "auto",
        },
        runtime_data=SimpleNamespace(
            data=SimpleNamespace(class_catalog={}),
            hass=SimpleNamespace(config=SimpleNamespace(language="en")),
            async_apply_option=Mock(),
        ),
    )
    options_flow = RecameraProOptionsFlow()
    options_flow.async_show_menu = Mock(
        side_effect=lambda **kw: {"type": FlowResultType.MENU, **kw}
    )
    options_flow.async_create_entry = Mock(
        side_effect=lambda **kw: {"type": FlowResultType.CREATE_ENTRY, **kw}
    )
    with patch.object(RecameraProOptionsFlow, "config_entry", new=entry):
        menu = await options_flow.async_step_init()
        assert menu["type"] == FlowResultType.MENU
        assert menu["menu_options"] == ["vision", "sound", "classes"]

        res = await options_flow.async_step_vision(
            {
                CONF_VISUAL_CONFIDENCE: 0.65,
                CONF_VISUAL_CONFIRM: 1.0,
                CONF_CLASS_STALE_SECONDS: 10.0,
                CONF_VISUAL_COOLDOWN: 3.0,
            }
        )
    assert res["type"] == FlowResultType.CREATE_ENTRY
    assert res["data"][CONF_VISUAL_CONFIDENCE] == 0.65
    assert entry.entry_id == "e1"
    assert getattr(entry, "unique_id", "SN123456") == "SN123456"


@pytest.mark.asyncio
async def test_options_flow_sound_classes_and_compatibility() -> None:
    """Test sound, classes, and compatibility options flow steps."""
    entry = SimpleNamespace(
        entry_id="e1",
        options={
            CONF_VISUAL_CONFIDENCE: 0.5,
            CONF_VISUAL_CONFIRM: 0.0,
            CONF_CLASS_STALE_SECONDS: 8.0,
            CONF_VISUAL_COOLDOWN: 2.0,
            CONF_AUDIO_CONFIDENCE: 0.8,
            CONF_AUDIO_COOLDOWN: 5.0,
            CONF_TRACKED_CLASSES: [],
            CONF_LANGUAGE: "auto",
        },
        runtime_data=SimpleNamespace(
            data=SimpleNamespace(class_catalog={}),
            hass=SimpleNamespace(config=SimpleNamespace(language="en")),
            async_apply_option=Mock(),
        ),
    )
    options_flow = RecameraProOptionsFlow()
    options_flow.hass = entry.runtime_data.hass
    options_flow.async_show_form = Mock(
        side_effect=lambda **kw: {"type": FlowResultType.FORM, **kw}
    )
    options_flow.async_create_entry = Mock(
        side_effect=lambda **kw: {"type": FlowResultType.CREATE_ENTRY, **kw}
    )
    with patch.object(RecameraProOptionsFlow, "config_entry", new=entry):
        sound_form = await options_flow.async_step_sound()
        assert sound_form["type"] == FlowResultType.FORM
        sound_res = await options_flow.async_step_sound(
            {CONF_AUDIO_CONFIDENCE: 0.75, CONF_AUDIO_COOLDOWN: 4.0}
        )
        assert sound_res["data"][CONF_AUDIO_CONFIDENCE] == 0.75

        classes_form = await options_flow.async_step_classes()
        assert classes_form["type"] == FlowResultType.FORM
        classes_res = await options_flow.async_step_classes({CONF_TRACKED_CLASSES: []})
        assert classes_res["data"][CONF_TRACKED_CLASSES] == []


@pytest.mark.asyncio
async def test_manual_and_reconfigure_error_paths() -> None:
    """Test manual step and reconfigure error handling."""
    flow = _make_flow()
    flow.hass.config_entries.async_schedule_reload = Mock()
    form = await flow.async_step_user()
    assert form["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(side_effect=RecameraConnectionError("offline")),
    ):
        err_res = await flow.async_step_user(
            {CONF_HOST: "192.168.10.22", CONF_USERNAME: "admin", CONF_PASSWORD: "pw"}
        )
    assert err_res["errors"]["base"] == "cannot_connect"

    entry = SimpleNamespace(
        entry_id="e1",
        unique_id="SN123456",
        update_listeners=[],
        data={
            CONF_HOST: "192.168.10.22",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "old_password",
            CONF_MAC_ADDRESS: "4a:f8:34:07:ab:3d",
            CONF_SERIAL_NUMBER: "SN123456",
        },
    )
    flow._get_reconfigure_entry = lambda: entry
    flow.async_update_reload_and_abort = Mock(
        return_value={"type": FlowResultType.ABORT, "reason": "reconfigure_successful"}
    )
    reconf_form = await flow.async_step_reconfigure()
    assert reconf_form["type"] == FlowResultType.FORM
    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(side_effect=RecameraAuthenticationError("bad")),
    ):
        reconf_err = await flow.async_step_reconfigure(
            {CONF_HOST: "192.168.10.22", CONF_USERNAME: "admin", CONF_PASSWORD: "bad"}
        )
    assert reconf_err["errors"]["base"] == "invalid_auth"
    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe()),
    ):
        reconf_ok = await flow.async_step_reconfigure(
            {CONF_HOST: "192.168.10.22", CONF_USERNAME: "admin", CONF_PASSWORD: "newpw"}
        )
    assert reconf_ok["type"] == FlowResultType.ABORT
    assert reconf_ok["reason"] == "reconfigure_successful"


@pytest.mark.asyncio
async def test_helpers_and_reachability() -> None:
    """Test config flow host reachability probing helpers."""
    fake_writer = SimpleNamespace(close=Mock(), wait_closed=AsyncMock())

    async def _fake_open(host: str, _port: int):
        if host == "192.168.42.1":
            return None, fake_writer
        raise OSError("unreachable")

    with patch(
        "homeassistant.components.recamera_pro.config_flow.asyncio.open_connection",
        side_effect=_fake_open,
    ):
        ordered = await _prioritize_reachable_hosts(["10.0.0.1", "192.168.42.1"])
        assert ordered == ["192.168.42.1", "10.0.0.1"]
        assert await _any_host_reachable(["10.0.0.1", "192.168.42.1"]) is True
        assert await _any_host_reachable(["10.0.0.1"]) is False


@pytest.mark.asyncio
async def test_options_catalog_store_fallback() -> None:
    """Test store fallback for class catalog when runtime_data is unavailable."""
    entry_no_rt = SimpleNamespace(entry_id="e1", runtime_data=None)

    class _FakeStore:
        def __class_getitem__(cls, _item: object) -> type[_FakeStore]:
            return cls

        def __init__(self, *_args: object) -> None:
            pass

        async def async_load(self) -> dict[str, object]:
            return {
                "class_catalog": [
                    {"source_id": "builtin", "class_id": "0", "class_name": "person"}
                ]
            }

    with patch(
        "homeassistant.components.recamera_pro.config_flow.Store",
        new=_FakeStore,
    ):
        catalog = await _options_catalog(entry_no_rt, SimpleNamespace())
    assert "builtin:person" in catalog


@pytest.mark.asyncio
async def test_zeroconf_confirm_error_paths_and_existing_entry_update() -> None:
    """Test zeroconf confirm error handling and existing entry host update."""
    flow = _make_flow()
    flow.hass.config_entries.async_schedule_reload = Mock()
    flow._discovery_mac = "4a:f8:34:07:ab:3d"
    flow._discovery_serial = "SN123456"
    flow._discovery_host = "192.168.42.1"
    flow._discovery_hosts = ["192.168.42.1"]
    flow._cancel_discovery_refresh = Mock()

    form = await flow.async_step_zeroconf_confirm()
    assert form["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(side_effect=RecameraAuthenticationError("bad")),
    ):
        auth_err = await flow.async_step_zeroconf_confirm(
            {CONF_HOST: "192.168.42.1", CONF_USERNAME: "admin", CONF_PASSWORD: "wrong"}
        )
    assert auth_err["errors"]["base"] == "invalid_auth"

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe(mac="aa:bb:cc:dd:ee:ff", serial="OTHER")),
    ):
        mismatch = await flow.async_step_zeroconf_confirm(
            {CONF_HOST: "192.168.42.1", CONF_USERNAME: "admin", CONF_PASSWORD: "ok"}
        )
    assert mismatch["errors"]["base"] == "identity_mismatch"
    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe()),
    ):
        recovered = await flow.async_step_zeroconf_confirm(
            {CONF_HOST: "192.168.42.1", CONF_USERNAME: "admin", CONF_PASSWORD: "ok"}
        )
    assert recovered["type"] == FlowResultType.CREATE_ENTRY
    assert flow.async_set_unique_id.call_args.args[0] == "SN123456"


@pytest.mark.asyncio
async def test_zeroconf_existing_entry_update() -> None:
    """Test zeroconf host update for existing configured entries."""
    flow = _make_flow()
    flow.hass.config_entries.async_schedule_reload = Mock()
    existing = SimpleNamespace(
        entry_id="e1",
        unique_id="SN123456",
        update_listeners=[],
        data={
            CONF_HOST: "192.168.10.22",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "pw",
            CONF_MAC_ADDRESS: "4a:f8:34:07:ab:3d",
            CONF_SERIAL_NUMBER: "SN123456",
            CONF_DEVICE_ID: "4a:f8:34:07:ab:3d",
        },
    )
    flow._async_current_entries = lambda: [existing]
    discovery_info = SimpleNamespace(
        name="reCamera Pro (4A:F8:34:07:AB:3D)._recamera._tcp.local.",
        type="_recamera._tcp.local.",
        host="192.168.42.1",
        addresses=["192.168.42.1"],
        properties={"mac": "4a:f8:34:07:ab:3d", "id": "SN123456"},
    )
    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe()),
    ):
        res = await flow.async_step_zeroconf(discovery_info)
    assert res["type"] == FlowResultType.ABORT
    assert res["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_probe_hosts_and_pending_discovery_helpers() -> None:
    """Test existing/new host probing error aggregation and pending flow lookup."""
    flow = _make_flow()
    flow.flow_id = "f1"
    entry = SimpleNamespace(
        entry_id="e1",
        unique_id="SN123456",
        data={
            CONF_HOST: "192.168.10.22",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "pw",
            CONF_MAC_ADDRESS: "4a:f8:34:07:ab:3d",
            CONF_SERIAL_NUMBER: "SN123456",
        },
    )
    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(side_effect=RecameraAuthenticationError("bad")),
    ):
        _, _, err = await flow._async_probe_existing_discovery_hosts(
            entry, ["192.168.42.1"]
        )
        assert err == "invalid_auth"
        _, _, err_new = await flow._async_probe_new_discovery_hosts(
            ["192.168.42.1"], "admin", "bad"
        )
        assert err_new == "invalid_auth"

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe(mac="aa:bb:cc:dd:ee:ff", serial="OTHER")),
    ):
        _, _, err_id = await flow._async_probe_existing_discovery_hosts(
            entry, ["192.168.42.1"]
        )
        assert err_id == "identity_mismatch"

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(side_effect=RecameraConnectionError("down")),
    ):
        _, _, err_conn = await flow._async_probe_existing_discovery_hosts(
            entry, ["192.168.42.1"]
        )
        assert err_conn == "cannot_connect"

    flow.hass.config_entries.flow.async_progress_by_handler = lambda _d: [
        {"context": {"source": "zeroconf", "unique_id": "4a:f8:34:07:ab:3d"}}
    ]
    assert flow._pending_discovery_flow("4a:f8:34:07:ab:3d") is not None
    assert flow._pending_discovery_flow("other") is None


@pytest.mark.asyncio
async def test_resolve_zeroconf_and_refresh_exit() -> None:
    """Test zeroconf resolution helper and refresh task cancellation/exit."""
    fake_info = SimpleNamespace(
        parsed_addresses=lambda: ["192.168.42.1", "169.254.1.2"],
        port=80,
        server="reCamera-Pro.local.",
        properties={b"mac": b"4a:f8:34:07:ab:3d"},
        decoded_properties={"mac": "4a:f8:34:07:ab:3d"},
        async_request=AsyncMock(return_value=True),
    )
    with (
        patch(
            "homeassistant.components.recamera_pro.config_flow.ha_zeroconf.async_get_async_instance",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    zeroconf=SimpleNamespace(
                        done=False,
                        cache=SimpleNamespace(async_all_by_details=lambda *_a: []),
                    )
                )
            ),
        ),
        patch(
            "homeassistant.components.recamera_pro.config_flow.AsyncServiceInfo",
            return_value=fake_info,
        ),
    ):
        resolved = await _async_resolve_zeroconf_service(
            SimpleNamespace(), "_recamera._tcp.local.", "recamera._recamera._tcp.local."
        )
    assert resolved is not None
    assert resolved[0] == ["192.168.42.1"]
    assert resolved[3]["mac"] == "4a:f8:34:07:ab:3d"

    flow = _make_flow()
    flow.flow_id = "f1"
    flow.hass.config_entries.flow.async_get = Mock(
        side_effect=data_entry_flow.UnknownFlow
    )
    await flow._async_refresh_discovery("_recamera._tcp.local.", "svc")


@pytest.mark.asyncio
async def test_config_flow_helper_edge_cases() -> None:
    """Test helper functions and zeroconf edge branches."""
    assert _text(b" abc ") == "abc"
    assert _text(None) == ""
    assert not _is_ignored_discovery_host("not-an-ip")
    assert await _prioritize_reachable_hosts(["192.168.1.1"]) == ["192.168.1.1"]

    fake_writer = SimpleNamespace(close=Mock(), wait_closed=AsyncMock())

    async def _first_ok(host: str, _port: int) -> tuple[None, SimpleNamespace]:
        if host == "192.168.1.10":
            return None, fake_writer
        raise OSError("down")

    with patch("asyncio.open_connection", side_effect=_first_ok):
        assert await _prioritize_reachable_hosts(["192.168.1.10", "192.168.1.20"]) == [
            "192.168.1.10",
            "192.168.1.20",
        ]
        assert await _prioritize_reachable_hosts(["192.168.1.20", "192.168.1.30"]) == [
            "192.168.1.20",
            "192.168.1.30",
        ]

    with patch(
        "homeassistant.components.recamera_pro.config_flow.async_probe_device",
        new=AsyncMock(return_value=_probe()),
    ) as probe_mock:
        res = await _async_probe_device_with_hass(None, "192.168.1.10", "admin", "pw")
    assert res.info.serial_number == "SN123456"
    probe_mock.assert_awaited_once_with("192.168.1.10", "admin", "pw")

    with patch(
        "homeassistant.components.recamera_pro.config_flow.ha_zeroconf.async_get_async_instance",
        new=AsyncMock(
            return_value=SimpleNamespace(zeroconf=SimpleNamespace(done=True))
        ),
    ):
        assert (
            await _async_resolve_zeroconf_service(
                SimpleNamespace(), "_recamera._tcp.local.", "svc"
            )
            is None
        )

    removed_records: list[str] = []
    fake_info = SimpleNamespace(
        parsed_addresses=lambda: ["bad-ip", "0.0.0.0", "192.168.42.1", "192.168.42.1"],
        port=80,
        server="reCamera-Pro.local.",
        decoded_properties={"mac": "4a:f8:34:07:ab:3d"},
        async_request=AsyncMock(return_value=True),
    )
    with (
        patch(
            "homeassistant.components.recamera_pro.config_flow.ha_zeroconf.async_get_async_instance",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    zeroconf=SimpleNamespace(
                        done=False,
                        cache=SimpleNamespace(
                            async_all_by_details=lambda *_a: ["rec1"],
                            async_remove_records=removed_records.extend,
                        ),
                    )
                )
            ),
        ),
        patch(
            "homeassistant.components.recamera_pro.config_flow.AsyncServiceInfo",
            return_value=fake_info,
        ),
    ):
        resolved = await _async_resolve_zeroconf_service(
            SimpleNamespace(), "_recamera._tcp.local.", "svc"
        )
    assert resolved is not None
    assert resolved[0] == ["192.168.42.1"]
    assert removed_records

    class _BadStore:
        def __class_getitem__(cls, _item: object) -> type[_BadStore]:
            return cls

        def __init__(self, *_a: object, **_kw: object) -> None:
            pass

        async def async_load(self) -> dict[str, object]:
            return {
                "class_catalog": [
                    "bad",
                    {"source_id": "builtin", "class_name": "person"},
                ],
                "discovered_classes": ["bad", ["builtin", "car"]],
            }

    with patch(
        "homeassistant.components.recamera_pro.config_flow.Store",
        new=_BadStore,
    ):
        cat = await _options_catalog(
            SimpleNamespace(entry_id="e1", runtime_data=None), SimpleNamespace()
        )
    assert "builtin:person" in cat
    assert "builtin:car" in cat


@pytest.mark.asyncio
async def test_user_reauth_reconfigure_and_options_forms() -> None:
    """Test all error/recovery paths in user, reauth, reconfigure, and options."""
    flow = _make_flow()
    assert isinstance(
        RecameraProConfigFlow.async_get_options_flow(SimpleNamespace()),
        RecameraProOptionsFlow,
    )

    user_form = await flow.async_step_user()
    assert user_form["type"] == FlowResultType.FORM

    for exc, expected_err in (
        (RecameraAuthenticationError("bad"), "invalid_auth"),
        (RecameraProtocolError("proto"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ):
        with patch(
            "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
            new=AsyncMock(side_effect=exc),
        ):
            err = await flow.async_step_user(
                {CONF_HOST: "192.168.10.22", CONF_USERNAME: "admin", CONF_PASSWORD: "p"}
            )
        assert err["errors"]["base"] == expected_err

    no_id_probe = RecameraProbeResult(
        info=RecameraDeviceInfo(
            base_plate_model="reCamera Pro",
            firmware_version="V1.3.0",
            serial_number=None,
            mac_address=None,
        ),
        capabilities={},
    )
    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=no_id_probe),
    ):
        no_id_err = await flow.async_step_user(
            {CONF_HOST: "192.168.10.22", CONF_USERNAME: "admin", CONF_PASSWORD: "p"}
        )
    assert no_id_err["errors"]["base"] == "identity_unavailable"

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe()),
    ):
        user_ok = await flow.async_step_user(
            {CONF_HOST: "192.168.10.22", CONF_USERNAME: "admin", CONF_PASSWORD: "p"}
        )
    assert user_ok["type"] == FlowResultType.CREATE_ENTRY
    assert flow.async_set_unique_id.call_args.args[0] == "SN123456"

    # Reauth form + error paths + recovery
    entry = SimpleNamespace(
        entry_id="e1",
        unique_id="SN123456",
        update_listeners=[],
        data={
            CONF_HOST: "192.168.10.22",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "old",
            CONF_MAC_ADDRESS: "4a:f8:34:07:ab:3d",
            CONF_SERIAL_NUMBER: "SN123456",
        },
    )
    flow._get_reauth_entry = lambda: entry
    flow._get_reconfigure_entry = lambda: entry
    flow.async_update_reload_and_abort = Mock(
        side_effect=lambda *_a, reason, **_kw: {
            "type": FlowResultType.ABORT,
            "reason": reason,
        }
    )

    reauth_form = await flow.async_step_reauth(entry.data)
    assert reauth_form["type"] == FlowResultType.FORM
    for exc, expected_err in (
        (RecameraAuthenticationError("bad"), "invalid_auth"),
        (RecameraError("conn"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ):
        with patch(
            "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
            new=AsyncMock(side_effect=exc),
        ):
            err = await flow.async_step_reauth_confirm(
                {CONF_USERNAME: "admin", CONF_PASSWORD: "bad"}
            )
        assert err["errors"]["base"] == expected_err

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe(mac="aa:bb:cc:dd:ee:ff", serial="OTHER")),
    ):
        mismatch = await flow.async_step_reauth_confirm(
            {CONF_USERNAME: "admin", CONF_PASSWORD: "ok"}
        )
    assert mismatch["errors"]["base"] == "identity_mismatch"

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe()),
    ):
        reauth_ok = await flow.async_step_reauth_confirm(
            {CONF_USERNAME: "admin", CONF_PASSWORD: "new"}
        )
    assert reauth_ok["type"] == FlowResultType.ABORT
    assert reauth_ok["reason"] == "reauth_successful"

    # Reconfigure error paths + recovery
    for exc, expected_err in (
        (RecameraError("conn"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ):
        with patch(
            "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
            new=AsyncMock(side_effect=exc),
        ):
            err = await flow.async_step_reconfigure(
                {CONF_HOST: "192.168.10.22", CONF_USERNAME: "admin", CONF_PASSWORD: "p"}
            )
        assert err["errors"]["base"] == expected_err

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe(mac="aa:bb:cc:dd:ee:ff", serial="OTHER")),
    ):
        reconf_mismatch = await flow.async_step_reconfigure(
            {CONF_HOST: "192.168.10.22", CONF_USERNAME: "admin", CONF_PASSWORD: "p"}
        )
    assert reconf_mismatch["errors"]["base"] == "identity_mismatch"

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe()),
    ):
        reconf_ok = await flow.async_step_reconfigure(
            {CONF_HOST: "192.168.10.22", CONF_USERNAME: "admin", CONF_PASSWORD: "new"}
        )
    assert reconf_ok["type"] == FlowResultType.ABORT
    assert reconf_ok["reason"] == "reconfigure_successful"

    # Options forms (GET without user_input)
    opts_entry = SimpleNamespace(
        entry_id="e1",
        options={},
        runtime_data=SimpleNamespace(data=SimpleNamespace(class_catalog={})),
    )
    options_flow = RecameraProOptionsFlow()
    with patch.object(RecameraProOptionsFlow, "config_entry", new=opts_entry):
        assert (await options_flow.async_step_vision())["type"] == FlowResultType.FORM
        assert (await options_flow.async_step_sound())["type"] == FlowResultType.FORM
        assert (await options_flow.async_step_classes())["type"] == FlowResultType.FORM


@pytest.mark.asyncio
async def test_zeroconf_and_discovery_refresh_branches() -> None:
    """Test zeroconf abort, validation, probing, and refresh loop branches."""
    flow = _make_flow()
    bad_type = SimpleNamespace(
        type="_http._tcp.local.",
        name="bad",
        host="192.168.10.22",
        properties={},
    )
    assert (await flow.async_step_zeroconf(bad_type))["reason"] == (
        "unsupported_discovery"
    )

    flow._discovery_serial = "SN123456"
    assert flow._canonical_discovery_identity() == "SN123456"
    assert flow._discovery_identity_mismatch(_probe(serial="OTHER"))
    flow._discovery_serial = None
    assert not flow._discovery_identity_mismatch(_probe())
    assert flow._canonical_discovery_identity() is None
    flow._discovery_id = "DISC1"
    assert flow._canonical_discovery_identity() == "DISC1"

    # Pending discovery flow -> already_in_progress
    flow.hass.config_entries.flow.async_progress_by_handler = lambda _d: [
        {"context": {"source": "zeroconf", "unique_id": "4a:f8:34:07:ab:3d"}}
    ]
    dup_info = SimpleNamespace(
        type="_recamera._tcp.local.",
        name="reCamera._recamera._tcp.local.",
        host="192.168.10.22",
        ip_addresses=["192.168.10.22"],
        properties={"mac": "4a:f8:34:07:ab:3d"},
    )
    with patch(
        "homeassistant.components.recamera_pro.config_flow._prioritize_reachable_hosts",
        new=AsyncMock(side_effect=list),
    ):
        dup_res = await flow.async_step_zeroconf(dup_info)
    assert dup_res["reason"] == "already_in_progress"

    # No canonical identity path -> _async_abort_entries_match
    flow.hass.config_entries.flow.async_progress_by_handler = list
    anon_info = SimpleNamespace(
        type="_recamera._tcp.local.",
        name="reCamera._recamera._tcp.local.",
        host="192.168.10.22",
        ip_addresses=["192.168.10.22"],
        properties={},
    )
    with patch(
        "homeassistant.components.recamera_pro.config_flow._prioritize_reachable_hosts",
        new=AsyncMock(side_effect=list),
    ):
        anon_res = await flow.async_step_zeroconf(anon_info)
    assert anon_res["type"] == FlowResultType.FORM

    # zeroconf_confirm identity_unavailable then recovery
    no_id_probe = RecameraProbeResult(
        info=RecameraDeviceInfo(
            base_plate_model="reCamera Pro",
            firmware_version="V1.3.0",
            serial_number=None,
            mac_address=None,
        ),
        capabilities={},
    )
    flow._discovery_host = "192.168.10.22"
    flow._discovery_hosts = ["192.168.10.22"]
    flow._discovery_id = "DISC1"
    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=no_id_probe),
    ):
        id_err = await flow.async_step_zeroconf_confirm(
            {CONF_HOST: "192.168.10.22", CONF_USERNAME: "admin", CONF_PASSWORD: "pw"}
        )
    assert id_err["errors"]["base"] == "identity_unavailable"
    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe()),
    ):
        ok_confirm = await flow.async_step_zeroconf_confirm(
            {CONF_HOST: "192.168.10.22", CONF_USERNAME: "admin", CONF_PASSWORD: "pw"}
        )
    assert ok_confirm["type"] == FlowResultType.CREATE_ENTRY
    assert flow.async_set_unique_id.call_args.args[0] == "SN123456"

    # _start_discovery_refresh & _cancel_discovery_refresh
    created_tasks: list[object] = []

    def _fake_create_task(coro: object, *, name: str) -> SimpleNamespace:
        coro.close()  # type: ignore[attr-defined]
        created_tasks.append(name)
        return SimpleNamespace(done=lambda: False, cancel=Mock())

    flow.hass.async_create_background_task = _fake_create_task
    flow._start_discovery_refresh("_recamera._tcp.local.", "svc")
    flow._start_discovery_refresh("_recamera._tcp.local.", "svc")
    assert len(created_tasks) == 1
    flow._cancel_discovery_refresh()

    # _async_probe_existing_discovery_hosts & _async_probe_new_discovery_hosts exceptions
    entry = SimpleNamespace(
        entry_id="e1",
        unique_id="SN123456",
        data={
            CONF_HOST: "192.168.10.22",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "pw",
            CONF_MAC_ADDRESS: "4a:f8:34:07:ab:3d",
            CONF_SERIAL_NUMBER: "SN123456",
        },
        runtime_data=SimpleNamespace(last_update_success=True),
    )
    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(side_effect=[TimeoutError("t"), RuntimeError("boom")]),
    ):
        _, _, ex_err = await flow._async_probe_existing_discovery_hosts(
            entry, ["192.168.10.22", "192.168.10.23"]
        )
    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(side_effect=[TimeoutError("t"), RuntimeError("boom")]),
    ):
        _, _, new_err = await flow._async_probe_new_discovery_hosts(
            ["192.168.10.22", "192.168.10.23"], "admin", "pw"
        )
    assert ex_err == "cannot_connect"
    assert new_err == "cannot_connect"

    with patch.object(
        asyncio.get_running_loop(),
        "time",
        side_effect=[0.0, 100.0, 0.0, 100.0],
    ):
        _, _, dl_ex = await flow._async_probe_existing_discovery_hosts(
            entry, ["192.168.10.22"]
        )
        _, _, dl_new = await flow._async_probe_new_discovery_hosts(
            ["192.168.10.22"], "admin", "pw"
        )
    assert dl_ex == "cannot_connect"
    assert dl_new == "cannot_connect"

    # _async_validate_discovery_update: failure, old_host_healthy=True, and old_host check error
    with patch.object(
        flow,
        "_async_probe_existing_discovery_hosts",
        new=AsyncMock(return_value=(None, None, "cannot_connect")),
    ):
        fail_upd = await flow._async_validate_discovery_update(
            entry, ["192.168.10.99"], "DISC1"
        )
    assert fail_upd["reason"] == "cannot_connect"

    with (
        patch.object(
            flow,
            "_async_probe_existing_discovery_hosts",
            new=AsyncMock(return_value=("192.168.10.99", _probe(), None)),
        ),
        patch(
            "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
            new=AsyncMock(return_value=_probe()),
        ),
    ):
        keep_old = await flow._async_validate_discovery_update(
            entry, ["192.168.10.99"], "DISC1"
        )
    assert keep_old["reason"] == "already_configured"
    assert flow.hass.config_entries.async_update_entry.called

    flow.async_update_reload_and_abort = Mock(
        return_value={"type": FlowResultType.ABORT, "reason": "already_configured"}
    )
    for old_exc in (RecameraError("old down"), RuntimeError("unexpected")):
        with (
            patch.object(
                flow,
                "_async_probe_existing_discovery_hosts",
                new=AsyncMock(return_value=("192.168.10.99", _probe(), None)),
            ),
            patch(
                "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
                new=AsyncMock(side_effect=old_exc),
            ),
        ):
            sw_new = await flow._async_validate_discovery_update(
                entry, "192.168.10.99", "DISC1"
            )
        assert sw_new["reason"] == "already_configured"
    assert flow.async_update_reload_and_abort.called

    # _async_refresh_discovery sequence exercising all main branches
    flow2 = _make_flow()
    flow2.flow_id = "f2"
    flow2.context = {}
    flow2._discovery_hosts = ["192.168.10.22"]
    flow2.hass.config_entries.flow.async_get = Mock(
        side_effect=[IndexError(), None, None, None, None, None, None, None, None, None]
    )
    flow2.hass.config_entries.flow.async_abort = Mock()
    resolve_seq = [
        NotRunningException(),
        RuntimeError("boom"),
        None,
        ([], 80, "reCamera.local.", {}),
        ([], 80, "reCamera.local.", {}),
        (["192.168.10.22"], 80, "reCamera.local.", {}),
        (["192.168.10.22", "192.168.10.23"], 80, "reCamera.local.", {}),
        (["192.168.10.99"], 80, "reCamera.local.", {}),
        (["192.168.10.99"], 80, "reCamera.local.", {}),
    ]
    with (
        patch(
            "homeassistant.components.recamera_pro.config_flow._async_resolve_zeroconf_service",
            new=AsyncMock(side_effect=resolve_seq),
        ),
        patch(
            "homeassistant.components.recamera_pro.config_flow._any_host_reachable",
            new=AsyncMock(side_effect=[True, True, False, False]),
        ),
        patch(
            "homeassistant.components.recamera_pro.config_flow.asyncio.sleep",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.recamera_pro.config_flow.discovery_flow.async_create_flow"
        ) as create_flow,
    ):
        await flow2._async_refresh_discovery("_recamera._tcp.local.", "svc")
    assert create_flow.called

    # Offline abort branch in _async_refresh_discovery
    flow3 = _make_flow()
    flow3.flow_id = "f3"
    flow3._discovery_hosts = ["192.168.10.22"]
    flow3.hass.config_entries.flow.async_get = Mock()
    flow3.hass.config_entries.flow.async_abort = Mock()
    with (
        patch(
            "homeassistant.components.recamera_pro.config_flow._async_resolve_zeroconf_service",
            new=AsyncMock(return_value=([], 80, "reCamera.local.", {})),
        ),
        patch(
            "homeassistant.components.recamera_pro.config_flow._any_host_reachable",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "homeassistant.components.recamera_pro.config_flow.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        await flow3._async_refresh_discovery("_recamera._tcp.local.", "svc")
    flow3.hass.config_entries.flow.async_abort.assert_called_once_with("f3")

    # _discovery_form_shown=True and UnknownFlow on final abort
    flow4 = _make_flow()
    flow4.flow_id = "f4"
    flow4._discovery_form_shown = True
    flow4._discovery_hosts = ["192.168.10.22"]
    flow4.hass.config_entries.flow.async_get = Mock()
    flow4.hass.config_entries.flow.async_abort = Mock(
        side_effect=data_entry_flow.UnknownFlow
    )
    with (
        patch(
            "homeassistant.components.recamera_pro.config_flow._async_resolve_zeroconf_service",
            new=AsyncMock(
                side_effect=[
                    (["192.168.10.55"], 80, "reCamera.local.", {}),
                    (["192.168.10.66"], 80, "reCamera.local.", {}),
                ]
            ),
        ),
        patch(
            "homeassistant.components.recamera_pro.config_flow._any_host_reachable",
            new=AsyncMock(side_effect=[False, True]),
        ),
        patch(
            "homeassistant.components.recamera_pro.config_flow.asyncio.sleep",
            new=AsyncMock(side_effect=[None, RuntimeError("stop")]),
        ),
    ):
        flow4._discovery_form_shown = True
        with pytest.raises(RuntimeError, match="stop"):
            await flow4._async_refresh_discovery("_recamera._tcp.local.", "svc")

    flow4._discovery_form_shown = False
    flow4._discovery_hosts = ["192.168.10.22"]
    flow4._discovery_refresh_candidate = ["192.168.10.66"]
    with (
        patch(
            "homeassistant.components.recamera_pro.config_flow._async_resolve_zeroconf_service",
            new=AsyncMock(return_value=(["192.168.10.66"], 80, "reCamera.local.", {})),
        ),
        patch(
            "homeassistant.components.recamera_pro.config_flow.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        await flow4._async_refresh_discovery("_recamera._tcp.local.", "svc")
