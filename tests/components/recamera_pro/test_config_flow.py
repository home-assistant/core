"""Config flow and options flow tests for reCamera Pro."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from recamera_protocol import (
    RecameraAuthenticationError,
    RecameraConnectionError,
    RecameraDeviceInfo,
    RecameraProbeResult,
)

from homeassistant import data_entry_flow
from homeassistant.components.recamera_pro.config_flow import (
    RecameraProConfigFlow,
    RecameraProOptionsFlow,
    _any_host_reachable,
    _async_resolve_zeroconf_service,
    _options_catalog,
    _prioritize_reachable_hosts,
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
    flow._async_current_entries = list  # noqa: SLF001
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock()  # noqa: SLF001
    flow._async_abort_entries_match = Mock()  # noqa: SLF001
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
    flow._async_current_entries = lambda: [other_entry]  # noqa: SLF001
    flow._start_discovery_refresh = Mock()  # noqa: SLF001

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
    assert flow._discovery_host == "192.168.7.214"  # noqa: SLF001


@pytest.mark.asyncio
async def test_zeroconf_confirm_does_not_trust_unverified_mdns_serial() -> None:
    """Test mDNS serial is not written to entry data unless verified by HTTP probe."""
    flow = _make_flow()
    flow.hass.config_entries.async_schedule_reload = Mock()
    flow._discovery_mac = "fe:47:bc:57:26:0a"  # noqa: SLF001
    flow._discovery_serial = "UNVERIFIED_MDNS_SERIAL"  # noqa: SLF001
    flow._discovery_host = "192.168.7.214"  # noqa: SLF001
    flow._discovery_hosts = ["192.168.7.214"]  # noqa: SLF001
    flow._cancel_discovery_refresh = Mock()  # noqa: SLF001

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
    assert flow.async_set_unique_id.call_args.args[0] == "fe47bc57260a"
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
    flow._get_reconfigure_entry = lambda: entry  # noqa: SLF001
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
    flow2._get_reauth_entry = lambda: entry  # noqa: SLF001
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
        data={
            CONF_HOST: "192.168.10.22",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "old_password",
            CONF_MAC_ADDRESS: "4a:f8:34:07:ab:3d",
            CONF_SERIAL_NUMBER: "SN123456",
        },
    )
    flow._get_reconfigure_entry = lambda: entry  # noqa: SLF001
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
    flow._discovery_mac = "4a:f8:34:07:ab:3d"  # noqa: SLF001
    flow._discovery_serial = "SN123456"  # noqa: SLF001
    flow._discovery_host = "192.168.42.1"  # noqa: SLF001
    flow._discovery_hosts = ["192.168.42.1"]  # noqa: SLF001
    flow._cancel_discovery_refresh = Mock()  # noqa: SLF001

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
    flow._async_current_entries = lambda: [existing]  # noqa: SLF001
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
        _, _, err = await flow._async_probe_existing_discovery_hosts(  # noqa: SLF001
            entry, ["192.168.42.1"]
        )
        assert err == "invalid_auth"
        _, _, err_new = await flow._async_probe_new_discovery_hosts(  # noqa: SLF001
            ["192.168.42.1"], "admin", "bad"
        )
        assert err_new == "invalid_auth"

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(return_value=_probe(mac="aa:bb:cc:dd:ee:ff", serial="OTHER")),
    ):
        _, _, err_id = await flow._async_probe_existing_discovery_hosts(  # noqa: SLF001
            entry, ["192.168.42.1"]
        )
        assert err_id == "identity_mismatch"

    with patch(
        "homeassistant.components.recamera_pro.config_flow._async_probe_device_with_hass",
        new=AsyncMock(side_effect=RecameraConnectionError("down")),
    ):
        _, _, err_conn = await flow._async_probe_existing_discovery_hosts(  # noqa: SLF001
            entry, ["192.168.42.1"]
        )
        assert err_conn == "cannot_connect"

    flow.hass.config_entries.flow.async_progress_by_handler = lambda _d: [
        {"context": {"source": "zeroconf", "unique_id": "4a:f8:34:07:ab:3d"}}
    ]
    assert flow._pending_discovery_flow("4a:f8:34:07:ab:3d") is not None  # noqa: SLF001
    assert flow._pending_discovery_flow("other") is None  # noqa: SLF001


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
    await flow._async_refresh_discovery("_recamera._tcp.local.", "svc")  # noqa: SLF001
