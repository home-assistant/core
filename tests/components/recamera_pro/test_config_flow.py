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

from homeassistant.components.recamera_pro.config_flow import (
    RecameraProConfigFlow,
    RecameraProOptionsFlow,
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
        new=AsyncMock(side_effect=lambda hosts: list(hosts)),
    ):
        res = await flow.async_step_zeroconf(discovery_info)
    assert res["type"] == FlowResultType.FORM
    assert flow._discovery_host == "192.168.7.214"  # noqa: SLF001


@pytest.mark.asyncio
async def test_zeroconf_confirm_does_not_trust_unverified_mdns_serial() -> None:
    """Test mDNS serial is not written to entry data unless verified by HTTP probe."""
    flow = _make_flow()
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
        assert set(menu["menu_options"]) >= {
            "vision",
            "sound",
            "classes",
            "compatibility",
        }

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
