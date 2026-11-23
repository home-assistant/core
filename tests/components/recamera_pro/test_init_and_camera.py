"""Setup, camera, capture controller, and coordinator tests for reCamera Pro."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from recamera_protocol import RecameraDeviceInfo, RecameraProtocolError

from homeassistant.components.camera import CameraEntityFeature
from homeassistant.components.recamera_pro import (
    _async_register_services,
    _normalize_entry_title,
)
from homeassistant.components.recamera_pro.camera import (
    RecameraMainstreamCamera,
    RecameraSubstreamCamera,
)
from homeassistant.components.recamera_pro.capture_controller import (
    CaptureController,
    CaptureOperation,
    CaptureState,
    CaptureTerminalFailureError,
)
from homeassistant.components.recamera_pro.coordinator import (
    FirmwareUpdateState,
    RecameraCoordinator,
)
from homeassistant.const import CONF_HOST


def test_register_services_and_custom_title_preservation() -> None:
    """Test platform service registration and custom entry title preservation."""
    with patch(
        "homeassistant.components.recamera_pro.service.async_register_platform_entity_service"
    ) as register:
        _async_register_services(SimpleNamespace())
    assert register.call_count == 3

    updated = Mock()
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=updated))
    custom_entry = SimpleNamespace(
        title="reCamera Pro (客厅)",
        data={CONF_HOST: "192.168.10.22", "mac_address": "4a:f8:34:07:ab:3d"},
    )
    _normalize_entry_title(hass, custom_entry)
    updated.assert_not_called()

    legacy_entry = SimpleNamespace(
        title="reCamera Pro (4A:F8:34:07:AB:3D)",
        data={
            CONF_HOST: "192.168.10.22",
            "mac_address": "4a:f8:34:07:ab:3d",
            "serial_number": "SN123456",
        },
    )
    _normalize_entry_title(hass, legacy_entry)
    updated.assert_called_once()


@pytest.mark.asyncio
async def test_camera_on_off_and_offline_placeholder() -> None:
    """Test camera stays available when RTSP is off and returns placeholder JPEG."""
    state = {"enabled": True}

    async def _set_enabled(_stream: str, enabled: bool) -> dict[str, object]:
        state["enabled"] = enabled
        return {"rtsp": {"iEnabled": 1 if enabled else 0}}

    coordinator = SimpleNamespace(
        device_id="dev1",
        last_update_success=True,
        connection_generation=1,
        config_entry=SimpleNamespace(
            data={CONF_HOST: "192.168.10.22"},
            options={},
            title="reCamera Pro",
            entry_id="e1",
        ),
        data=None,
        is_stream_enabled=lambda _s: state["enabled"],
        get_stream_url=lambda _s: "rtsp://1.2.3.4/sub" if state["enabled"] else None,
        async_set_stream_enabled=AsyncMock(side_effect=_set_enabled),
        async_capture_device_snapshot=AsyncMock(
            return_value={"capture": {"sStatus": "COMPLETED"}}
        ),
    )
    sub = RecameraSubstreamCamera(coordinator)
    main = RecameraMainstreamCamera(coordinator)
    assert sub.supported_features == (
        CameraEntityFeature.STREAM | CameraEntityFeature.ON_OFF
    )
    assert main.entity_registry_enabled_default is False

    fake_stream = SimpleNamespace(stop=AsyncMock())
    sub.stream = fake_stream
    await sub.async_turn_off()
    assert not sub.is_on
    assert sub.available
    assert sub.extra_state_attributes["rtsp_enabled"] is False
    assert await sub.stream_source() is None
    offline_img = await sub.async_camera_image()
    assert offline_img is not None
    assert offline_img.startswith(b"\xff\xd8\xff")

    snap = await sub.async_capture_device_snapshot("/mnt/test.jpg")
    assert snap["capture"]["sStatus"] == "COMPLETED"

    await sub.async_turn_on()
    assert sub.is_on
    assert sub.extra_state_attributes["rtsp_enabled"] is True


@pytest.mark.asyncio
async def test_capture_controller_error_classification_and_shutdown() -> None:
    """Test generic protocol errors stay UNKNOWN while terminal errors mark FAILED."""
    controller = CaptureController(
        SimpleNamespace(bus=SimpleNamespace(async_fire=Mock())),
        SimpleNamespace(
            async_start_capture=AsyncMock(
                side_effect=RecameraProtocolError("invalid_json")
            )
        ),
        device_id="dev1",
        entry_id=None,
    )
    op = CaptureOperation(kind="snapshot", request_id="r1", fingerprint="fp1")
    with (
        patch.object(
            controller,
            "_async_reconcile_snapshot",
            new=AsyncMock(side_effect=RecameraProtocolError("invalid_json")),
        ),
        pytest.raises(RecameraProtocolError),
    ):
        await controller._async_run_snapshot(op, "/mnt/test.jpg")  # noqa: SLF001
    assert op.state == CaptureState.UNKNOWN

    op2 = CaptureOperation(kind="snapshot", request_id="r2", fingerprint="fp2")
    with (
        patch.object(
            controller,
            "_async_reconcile_snapshot",
            new=AsyncMock(side_effect=CaptureTerminalFailureError("capture_failed")),
        ),
        pytest.raises(CaptureTerminalFailureError),
    ):
        await controller._async_run_snapshot(op2, "/mnt/test.jpg")  # noqa: SLF001
    assert op2.state == CaptureState.FAILED

    controller._operation = op2  # noqa: SLF001
    await controller.async_shutdown()
    assert op2.completion_event.is_set()


@pytest.mark.asyncio
async def test_external_ota_continues_polling_and_stream_stop_order() -> None:
    """Test external OTA polls to completion and stream stop runs before device off."""
    order: list[str] = []
    coord = object.__new__(RecameraCoordinator)
    coord._firmware_reboot = None
    coord._firmware_lock = asyncio.Lock()
    coord._firmware_update = FirmwareUpdateState(
        installed_version="V1.3.0",
        in_progress=True,
        status="updating",
        operation="external",
    )
    coord.data = SimpleNamespace(info=RecameraDeviceInfo(firmware_version="V1.3.0"))
    coord.async_update_listeners = Mock()
    coord._stream_stop_callbacks = {}
    coord._cached_stream_info = {}
    coord.client = SimpleNamespace(
        async_check_firmware_update=AsyncMock(
            return_value={
                "iUpdateAvailable": False,
                "sCurrentVersion": "V1.3.1",
                "sLatestVersion": "V1.3.1",
                "sUpdating": False,
            }
        ),
        async_set_rtsp_stream_enabled=AsyncMock(
            side_effect=lambda _sid, _en: (
                order.append("device") or {"rtsp": {"iEnabled": 0}}
            )
        ),
    )

    state = await coord.async_check_firmware_update(force=True)
    assert not state.in_progress
    assert state.status == "idle"
    assert state.operation is None

    async def _stop_cb() -> None:
        order.append("ha_stream_stop")

    coord.data = None
    unsub = coord.register_stream_stop_callback("sub", _stop_cb)
    await coord.async_set_stream_enabled("sub", False)
    assert order == ["ha_stream_stop", "device"]
    unsub()
