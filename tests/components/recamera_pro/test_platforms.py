"""Platform entity and diagnostics tests for reCamera Pro."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from recamera_protocol import DetectedClass, ResultObservation

from homeassistant.components.recamera_pro.binary_sensor import (
    RecameraClassBinarySensor,
    RecameraMotionBinarySensor,
)
from homeassistant.components.recamera_pro.const import (
    CONF_DEVICE_ID,
    CONF_MAC_ADDRESS,
    CONF_SERIAL_NUMBER,
    SOURCE_AVAILABLE,
)
from homeassistant.components.recamera_pro.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.recamera_pro.event import (
    RecameraMotionEvent,
    RecameraSoundEvent,
    RecameraYoloEvent,
)
from homeassistant.components.recamera_pro.number import _numeric_value
from homeassistant.components.recamera_pro.sensor import VISUAL_SENSORS, RecameraSensor
from homeassistant.components.recamera_pro.source_state import DetectionState
from homeassistant.components.recamera_pro.update import RecameraFirmwareUpdate
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME


def _mock_coordinator() -> SimpleNamespace:
    now = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    obs = ResultObservation(
        source_id="builtin",
        source_kind="vision",
        task_type="detect",
        class_id="0",
        class_name="person",
        confidence=0.92,
        box=None,
        timestamp=now,
        device_wall_ms=1795413000000,
        received_at=now,
        clock_valid=True,
        event_id="evt-1",
    )
    visual = DetectionState(
        health=SOURCE_AVAILABLE,
        last_observation=obs,
        summary_observation=obs,
        active_classes={obs.class_key},
    )
    audio = DetectionState(health=SOURCE_AVAILABLE)
    motion = SimpleNamespace(
        installed=True,
        running=True,
        motion=True,
        app_health=SOURCE_AVAILABLE,
        enabled=True,
        detected=True,
        last_detected_at=now,
        events=(),
    )
    runtime = SimpleNamespace(
        info=SimpleNamespace(
            mac_address="4a:f8:34:07:ab:3d",
            serial_number="SN123456",
            base_plate_model="reCamera Pro",
            hardware_version="V1.0",
            firmware_version="V1.3.0",
        ),
        visual=visual,
        audio=audio,
        motion=motion,
        online=True,
        stream_ready=True,
        device_settings={"brightness": 50},
        media_profiles={"sub": {"encode": {"sResolution": "1280x720"}}},
        media_errors={},
        system_info={"firmware": "V1.3.0"},
        class_catalog={},
        motion_app_config={},
    )
    return SimpleNamespace(
        device_id="dev1",
        last_update_success=True,
        data=runtime,
        client=SimpleNamespace(host="192.168.10.22"),
        hass=SimpleNamespace(config=SimpleNamespace(language="en")),
        config_entry=SimpleNamespace(
            entry_id="e1",
            version=1,
            title="reCamera Pro",
            data={
                CONF_HOST: "192.168.10.22",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "secret_password",
                CONF_MAC_ADDRESS: "4a:f8:34:07:ab:3d",
                CONF_SERIAL_NUMBER: "SN123456",
                CONF_DEVICE_ID: "dev1",
            },
            options={},
        ),
        effective_language=lambda: "en",
        class_entity_unique_id=lambda cls: f"dev1_{cls.key}",
        class_is_active=lambda cls: cls.class_name == "person",
        is_class_present=lambda cls: cls.class_name == "person",
        firmware_update=SimpleNamespace(
            latest_version="V1.3.1",
            release_url="https://github.com/Seeed-Studio/reCamera-Pro",
            release_summary="Bug fixes",
            in_progress=False,
            update_percentage=None,
            checked=True,
        ),
        async_install_firmware_update=AsyncMock(),
        async_check_firmware_update=AsyncMock(
            return_value=SimpleNamespace(
                installed_version="V1.3.0",
                latest_version="V1.3.1",
                release_url="https://github.com/Seeed-Studio/reCamera-Pro",
                release_summary="Bug fixes",
                title="reCamera Pro Firmware",
            )
        ),
        async_add_listener=lambda _cb: lambda: None,
    )


def test_binary_sensor_and_summary_sensor_states() -> None:
    """Test binary sensors and summary sensor state rendering."""
    coordinator = _mock_coordinator()
    person_cls = DetectedClass(
        source_id="builtin",
        class_id="0",
        class_name="person",
    )
    target = RecameraClassBinarySensor(coordinator, person_cls)
    motion = RecameraMotionBinarySensor(coordinator)
    assert target.is_on is True
    assert motion.is_on is True

    summary_desc = next(d for d in VISUAL_SENSORS if d.source_id == "visual")
    summary = RecameraSensor(coordinator, summary_desc)
    assert summary.native_value == "person"
    assert summary.extra_state_attributes["source_status"] == SOURCE_AVAILABLE


def test_event_entities_and_numeric_helper() -> None:
    """Test event entities and number parsing helper."""
    coordinator = _mock_coordinator()
    yolo = RecameraYoloEvent(coordinator)
    sound = RecameraSoundEvent(coordinator)
    motion = RecameraMotionEvent(coordinator)
    assert yolo.unique_id == "dev1_visual_event"
    assert sound.unique_id == "dev1_audio_event"
    assert len(motion.event_types) >= 1

    assert _numeric_value("42.5") == 42.5
    assert _numeric_value(float("nan")) is None
    assert _numeric_value("bad") is None


@pytest.mark.asyncio
async def test_diagnostics_redacts_secrets_and_update_entity() -> None:
    """Test diagnostics redaction and firmware update entity."""
    coordinator = _mock_coordinator()
    diag = await async_get_config_entry_diagnostics(
        coordinator.hass, coordinator.config_entry
    )
    assert CONF_PASSWORD not in diag["entry"]["data"]
    assert diag["entry"]["data"]["password_set"] is True
    assert diag["entry"]["data"][CONF_HOST] == "[redacted]"

    update_entity = RecameraFirmwareUpdate(coordinator)
    await update_entity.async_update()
    assert update_entity.installed_version == "V1.3.0"
    assert update_entity.latest_version == "V1.3.1"
    await update_entity.async_install("V1.3.1", False)
    coordinator.async_install_firmware_update.assert_awaited_once()
