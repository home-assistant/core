"""Tests for locknalert_mqtt util module."""

import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.locknalert_mqtt.const import (
    ATTR_PAYLOAD,
    ATTR_QOS,
    ATTR_RETAIN,
    ATTR_TOPIC,
)
from homeassistant.components.locknalert_mqtt.models import DATA_MQTT, ReceiveMessage
from homeassistant.components.locknalert_mqtt.util import (
    EnsureJobAfterCooldown,
    async_cleanup_device_registry,
    async_create_certificate_temp_files,
    async_wait_for_mqtt_client,
    check_state_too_long,
    get_file_path,
    learn_more_url,
    migrate_certificate_file_to_content,
    mqtt_config_entry_enabled,
    platforms_from_config,
    valid_birth_will,
    valid_publish_topic,
    valid_qos_schema,
    valid_subscribe_topic,
    valid_subscribe_topic_template,
    valid_topic,
)
from homeassistant.const import MAX_LENGTH_STATE_STATE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from tests.typing import MqttMockHAClientGenerator


# ---------------------------------------------------------------------------
# valid_topic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "topic",
    ["sensor/temperature", "home/+/status", "home/#", "#", "+"],
    ids=["simple", "plus", "hash", "hash_only", "plus_only"],
)
def test_valid_topic_accepts_valid_topics(topic: str) -> None:
    """valid_topic returns the topic unchanged when it is well-formed."""
    assert valid_topic(topic) == topic


def test_valid_topic_rejects_empty_string() -> None:
    """Empty topic raises vol.Invalid."""
    with pytest.raises(vol.Invalid, match="must not be empty"):
        valid_topic("")


def test_valid_topic_rejects_null_character() -> None:
    """Topic with null byte raises vol.Invalid."""
    with pytest.raises(vol.Invalid, match="null character"):
        valid_topic("sen\x00sor")


def test_valid_topic_rejects_control_character_low() -> None:
    """Topic with low control character raises vol.Invalid."""
    with pytest.raises(vol.Invalid, match="control characters"):
        valid_topic("sen\x01sor")


def test_valid_topic_rejects_control_character_high() -> None:
    """Topic with high control character (U+0080) raises vol.Invalid."""
    with pytest.raises(vol.Invalid, match="control characters"):
        valid_topic("sen\x80sor")


def test_valid_topic_rejects_non_character() -> None:
    """Topic with a Unicode non-character raises vol.Invalid."""
    with pytest.raises(vol.Invalid, match="non-characters"):
        valid_topic("sen﷐sor")


def test_valid_topic_rejects_too_long() -> None:
    """Topic encoded to more than 65535 bytes raises vol.Invalid."""
    with pytest.raises(vol.Invalid, match="65535"):
        valid_topic("a" * 65536)


# ---------------------------------------------------------------------------
# valid_subscribe_topic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "topic",
    [
        "sensor/+/value",
        "home/+",
        "+/sensor",
        "sensor/#",
        "#",
        "home/+/+/state",
    ],
    ids=[
        "plus_middle",
        "plus_end",
        "plus_start",
        "hash_end",
        "hash_only",
        "multiple_plus",
    ],
)
def test_valid_subscribe_topic_accepts_valid_filters(topic: str) -> None:
    """valid_subscribe_topic accepts all well-formed wildcard placements."""
    assert valid_subscribe_topic(topic) == topic


def test_valid_subscribe_topic_rejects_plus_not_full_level() -> None:
    """+ embedded in a level segment raises vol.Invalid."""
    with pytest.raises(vol.Invalid, match="Single-level wildcard"):
        valid_subscribe_topic("sens+r/value")


def test_valid_subscribe_topic_rejects_hash_not_last() -> None:
    """# not at the end raises vol.Invalid."""
    with pytest.raises(vol.Invalid, match="last character"):
        valid_subscribe_topic("home/#/more")


def test_valid_subscribe_topic_rejects_hash_without_separator() -> None:
    """# not preceded by / (and not the whole filter) raises vol.Invalid."""
    with pytest.raises(vol.Invalid, match="separator"):
        valid_subscribe_topic("sensor#")


# ---------------------------------------------------------------------------
# valid_publish_topic
# ---------------------------------------------------------------------------


def test_valid_publish_topic_accepts_simple_topic() -> None:
    """valid_publish_topic returns clean topics unchanged."""
    assert valid_publish_topic("home/sensor/temp") == "home/sensor/temp"


@pytest.mark.parametrize(
    "topic",
    ["home/+/temp", "home/#", "home/+"],
    ids=["plus_wildcard", "hash_wildcard", "plus_only"],
)
def test_valid_publish_topic_rejects_wildcards(topic: str) -> None:
    """valid_publish_topic rejects any topic containing wildcards."""
    with pytest.raises(vol.Invalid, match="Wildcards"):
        valid_publish_topic(topic)


# ---------------------------------------------------------------------------
# valid_subscribe_topic_template
# ---------------------------------------------------------------------------


def test_valid_subscribe_topic_template_static() -> None:
    """Static value is validated as a subscribe topic and returned as Template."""
    result = valid_subscribe_topic_template("sensor/+/value")
    assert result.template == "sensor/+/value"


def test_valid_subscribe_topic_template_jinja() -> None:
    """Jinja2 template is accepted without subscribe-topic validation."""
    result = valid_subscribe_topic_template("sensor/{{ name }}/value")
    assert result.template == "sensor/{{ name }}/value"


def test_valid_subscribe_topic_template_static_invalid() -> None:
    """Static template that fails subscribe-topic validation raises vol.Invalid."""
    with pytest.raises(vol.Invalid):
        valid_subscribe_topic_template("sens+r/bad")


# ---------------------------------------------------------------------------
# valid_qos_schema
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("qos", [0, 1, 2], ids=["qos_0", "qos_1", "qos_2"])
def test_valid_qos_schema_accepts_valid_values(qos: int) -> None:
    """valid_qos_schema accepts 0, 1, and 2."""
    assert valid_qos_schema(qos) == qos


def test_valid_qos_schema_rejects_invalid() -> None:
    """valid_qos_schema rejects values outside 0-2."""
    with pytest.raises(vol.Invalid):
        valid_qos_schema(3)


# ---------------------------------------------------------------------------
# valid_birth_will
# ---------------------------------------------------------------------------


def test_valid_birth_will_empty_config() -> None:
    """Empty dict is returned unchanged (no birth/will configured)."""
    assert valid_birth_will({}) == {}


def test_valid_birth_will_falsy_config() -> None:
    """Falsy value is returned unchanged."""
    assert valid_birth_will(None) is None


def test_valid_birth_will_valid_config() -> None:
    """Valid birth/will config passes schema validation."""
    config = {
        ATTR_TOPIC: "home/status",
        ATTR_PAYLOAD: "online",
        ATTR_QOS: 0,
        ATTR_RETAIN: False,
    }
    result = valid_birth_will(config)
    assert result[ATTR_TOPIC] == "home/status"
    assert result[ATTR_PAYLOAD] == "online"


def test_valid_birth_will_invalid_topic_raises() -> None:
    """Birth/will config with wildcard topic raises vol.Invalid."""
    config = {ATTR_TOPIC: "home/#", ATTR_PAYLOAD: "online"}
    with pytest.raises(vol.Invalid):
        valid_birth_will(config)


# ---------------------------------------------------------------------------
# check_state_too_long
# ---------------------------------------------------------------------------


def test_check_state_too_long_short_state() -> None:
    """Returns False and does not log when state is within limit."""
    msg = MagicMock(spec=ReceiveMessage)
    msg.topic = "test/topic"
    logger = logging.getLogger("test")
    assert check_state_too_long(logger, "short", "sensor.test", msg) is False


def test_check_state_too_long_too_long_state(caplog: pytest.LogCaptureFixture) -> None:
    """Returns True and logs a warning when state exceeds the limit."""
    msg = MagicMock(spec=ReceiveMessage)
    msg.topic = "test/topic"
    logger = logging.getLogger("test_check_state")
    long_state = "x" * (MAX_LENGTH_STATE_STATE + 1)
    with caplog.at_level(logging.WARNING, logger="test_check_state"):
        result = check_state_too_long(logger, long_state, "sensor.test", msg)
    assert result is True
    assert "exceeds" in caplog.text


# ---------------------------------------------------------------------------
# get_file_path
# ---------------------------------------------------------------------------


def test_get_file_path_no_temp_dir(tmp_path: Path) -> None:
    """Returns default when temp dir does not exist."""
    with (
        patch(
            "homeassistant.components.locknalert_mqtt.util.tempfile.gettempdir",
            return_value=tmp_path,
        ),
        patch(
            "homeassistant.components.locknalert_mqtt.util.TEMP_DIR_NAME",
            "nonexistent-dir",
        ),
    ):
        assert get_file_path("certificate", "default_val") == "default_val"


def test_get_file_path_file_not_present(tmp_path: Path) -> None:
    """Returns default when dir exists but file does not."""
    dir_name = "test-cert-dir"
    cert_dir = tmp_path / dir_name
    cert_dir.mkdir()
    with (
        patch(
            "homeassistant.components.locknalert_mqtt.util.tempfile.gettempdir",
            return_value=tmp_path,
        ),
        patch(
            "homeassistant.components.locknalert_mqtt.util.TEMP_DIR_NAME",
            dir_name,
        ),
    ):
        assert get_file_path("certificate", None) is None


def test_get_file_path_file_present(tmp_path: Path) -> None:
    """Returns the file path string when the file exists."""
    dir_name = "test-cert-dir2"
    cert_dir = tmp_path / dir_name
    cert_dir.mkdir()
    (cert_dir / "certificate").write_text("cert-data")
    with (
        patch(
            "homeassistant.components.locknalert_mqtt.util.tempfile.gettempdir",
            return_value=tmp_path,
        ),
        patch(
            "homeassistant.components.locknalert_mqtt.util.TEMP_DIR_NAME",
            dir_name,
        ),
    ):
        result = get_file_path("certificate")
        assert result is not None
        assert result.endswith("certificate")


# ---------------------------------------------------------------------------
# migrate_certificate_file_to_content
# ---------------------------------------------------------------------------


def test_migrate_certificate_file_to_content_auto() -> None:
    """'auto' is returned as-is without reading any file."""
    assert migrate_certificate_file_to_content("auto") == "auto"


def test_migrate_certificate_file_to_content_reads_file(tmp_path: Path) -> None:
    """Reads and returns file content for a valid file path."""
    cert_file = tmp_path / "cert.pem"
    cert_file.write_text("PEM DATA")
    assert migrate_certificate_file_to_content(str(cert_file)) == "PEM DATA"


def test_migrate_certificate_file_to_content_missing_file() -> None:
    """Returns None when the file does not exist."""
    assert migrate_certificate_file_to_content("/nonexistent/path/cert.pem") is None


# ---------------------------------------------------------------------------
# learn_more_url
# ---------------------------------------------------------------------------


def test_learn_more_url() -> None:
    """Returns the HA documentation URL for the given platform."""
    url = learn_more_url("alarm_control_panel")
    assert url == "https://www.home-assistant.io/integrations/alarm_control_panel.mqtt/"


# ---------------------------------------------------------------------------
# platforms_from_config
# ---------------------------------------------------------------------------


def test_platforms_from_config_empty() -> None:
    """Empty config list returns empty set."""
    assert platforms_from_config([]) == set()


def test_platforms_from_config_single_platform() -> None:
    """Returns platform keys from a single-item config list."""
    result = platforms_from_config([{"alarm_control_panel": []}])
    assert result == {"alarm_control_panel"}


def test_platforms_from_config_multiple_platforms() -> None:
    """Returns union of all platform keys across multiple config dicts."""
    result = platforms_from_config(
        [{"alarm_control_panel": []}, {"sensor": []}, {"alarm_control_panel": []}]
    )
    assert result == {"alarm_control_panel", "sensor"}


# ---------------------------------------------------------------------------
# async_create_certificate_temp_files
# ---------------------------------------------------------------------------


async def test_async_create_certificate_temp_files_writes_files(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Certificate content is written to the temp directory."""
    dir_name = "test-cert-write"
    with (
        patch(
            "homeassistant.components.locknalert_mqtt.util.tempfile.gettempdir",
            return_value=tmp_path,
        ),
        patch(
            "homeassistant.components.locknalert_mqtt.util.TEMP_DIR_NAME",
            dir_name,
        ),
    ):
        await async_create_certificate_temp_files(
            hass,
            {
                "certificate": "CA CERT DATA",
                "client_cert": None,
                "client_key": None,
            },
        )
        cert_dir = tmp_path / dir_name
        assert (cert_dir / "certificate").read_text() == "CA CERT DATA"
        assert not (cert_dir / "client_cert").exists()


async def test_async_create_certificate_temp_files_removes_on_none(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Existing cert file is removed when value is set to None."""
    dir_name = "test-cert-remove"
    cert_dir = tmp_path / dir_name
    cert_dir.mkdir(mode=0o700)
    (cert_dir / "certificate").write_text("old data")
    with (
        patch(
            "homeassistant.components.locknalert_mqtt.util.tempfile.gettempdir",
            return_value=tmp_path,
        ),
        patch(
            "homeassistant.components.locknalert_mqtt.util.TEMP_DIR_NAME",
            dir_name,
        ),
    ):
        await async_create_certificate_temp_files(
            hass,
            {"certificate": None, "client_cert": None, "client_key": None},
        )
        assert not (cert_dir / "certificate").exists()


async def test_async_create_certificate_temp_files_auto_not_written(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """'auto' value removes any existing file rather than writing it."""
    dir_name = "test-cert-auto"
    cert_dir = tmp_path / dir_name
    cert_dir.mkdir(mode=0o700)
    (cert_dir / "certificate").write_text("old")
    with (
        patch(
            "homeassistant.components.locknalert_mqtt.util.tempfile.gettempdir",
            return_value=tmp_path,
        ),
        patch(
            "homeassistant.components.locknalert_mqtt.util.TEMP_DIR_NAME",
            dir_name,
        ),
    ):
        await async_create_certificate_temp_files(
            hass,
            {"certificate": "auto", "client_cert": None, "client_key": None},
        )
        assert not (cert_dir / "certificate").exists()


# ---------------------------------------------------------------------------
# mqtt_config_entry_enabled
# ---------------------------------------------------------------------------


async def test_mqtt_config_entry_enabled_when_connected(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Returns True when the MQTT client is connected."""
    await mqtt_mock_entry()
    assert mqtt_config_entry_enabled(hass) is True


async def test_mqtt_config_entry_enabled_no_data(hass: HomeAssistant) -> None:
    """Returns False when DATA_MQTT is not in hass.data and no config entries."""
    assert mqtt_config_entry_enabled(hass) is False


# ---------------------------------------------------------------------------
# async_wait_for_mqtt_client
# ---------------------------------------------------------------------------


async def test_async_wait_for_mqtt_client_returns_true_when_loaded(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Returns True immediately when config entry is LOADED."""
    await mqtt_mock_entry()
    result = await async_wait_for_mqtt_client(hass)
    assert result is True


async def test_async_wait_for_mqtt_client_returns_false_when_not_configured(
    hass: HomeAssistant,
) -> None:
    """Returns False immediately when no locknalert_mqtt config entry exists."""
    result = await async_wait_for_mqtt_client(hass)
    assert result is False


# ---------------------------------------------------------------------------
# async_cleanup_device_registry
# ---------------------------------------------------------------------------


async def test_async_cleanup_device_registry_removes_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Config entry link is removed from device when no entities remain."""
    await mqtt_mock_entry()
    device_registry = dr.async_get(hass)
    config_entry = hass.config_entries.async_entries("locknalert_mqtt")[0]
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("locknalert_mqtt", "test_device")},
        name="Test Device",
    )
    await async_cleanup_device_registry(hass, device.id, config_entry.entry_id)
    updated = device_registry.async_get(device.id)
    assert updated is None or config_entry.entry_id not in (
        updated.config_entries if updated else set()
    )


async def test_async_cleanup_device_registry_noop_when_device_id_none(
    hass: HomeAssistant,
) -> None:
    """Does nothing when device_id is None."""
    await async_cleanup_device_registry(hass, None, "some-entry-id")


async def test_async_cleanup_device_registry_noop_when_config_entry_id_none(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Does nothing when config_entry_id is None."""
    await mqtt_mock_entry()
    device_registry = dr.async_get(hass)
    config_entry = hass.config_entries.async_entries("locknalert_mqtt")[0]
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("locknalert_mqtt", "test_device_2")},
        name="Test Device 2",
    )
    await async_cleanup_device_registry(hass, device.id, None)


# ---------------------------------------------------------------------------
# EnsureJobAfterCooldown
# ---------------------------------------------------------------------------


async def test_ensure_job_after_cooldown_executes_callback() -> None:
    """async_execute runs the callback job."""
    executed = asyncio.Event()

    async def callback_job() -> None:
        executed.set()

    debouncer = EnsureJobAfterCooldown(0.0, callback_job)
    task = debouncer.async_execute()
    await task
    assert executed.is_set()


async def test_ensure_job_after_cooldown_schedules_followup_when_running() -> None:
    """If a task is running, async_execute schedules a follow-up instead."""
    call_count = 0
    ready = asyncio.Event()

    async def callback_job() -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await ready.wait()

    debouncer = EnsureJobAfterCooldown(0.0, callback_job)
    task = debouncer.async_execute()
    debouncer.async_execute()
    ready.set()
    await task
    await asyncio.sleep(0)
    assert call_count >= 1


async def test_ensure_job_after_cooldown_cleanup_cancels_task() -> None:
    """async_cleanup cancels an in-progress task."""
    started = asyncio.Event()

    async def long_job() -> None:
        started.set()
        await asyncio.sleep(10)

    debouncer = EnsureJobAfterCooldown(0.0, long_job)
    debouncer.async_execute()
    await started.wait()
    await debouncer.async_cleanup()
    assert debouncer._task is None


async def test_ensure_job_after_cooldown_cleanup_noop_when_idle() -> None:
    """async_cleanup does nothing when no task or timer is active."""
    debouncer = EnsureJobAfterCooldown(10.0, AsyncMock())
    await debouncer.async_cleanup()


async def test_ensure_job_after_cooldown_logs_ha_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """HomeAssistantError raised in the callback is logged, not propagated."""
    async def failing_job() -> None:
        raise HomeAssistantError("something went wrong")

    debouncer = EnsureJobAfterCooldown(0.0, failing_job)
    with caplog.at_level(logging.ERROR):
        task = debouncer.async_execute()
        await task
    assert "something went wrong" in caplog.text


async def test_ensure_job_after_cooldown_set_timeout() -> None:
    """set_timeout updates the cooldown period."""
    debouncer = EnsureJobAfterCooldown(5.0, AsyncMock())
    debouncer.set_timeout(1.0)
    assert debouncer._timeout == 1.0


async def test_ensure_job_after_cooldown_schedule_creates_timer() -> None:
    """async_schedule sets a timer when none exists."""
    debouncer = EnsureJobAfterCooldown(0.1, AsyncMock())
    assert debouncer._timer is None
    debouncer.async_schedule()
    assert debouncer._timer is not None
    debouncer._async_cancel_timer()


async def test_ensure_job_after_cooldown_schedule_extends_when_later() -> None:
    """async_schedule pushes _next_execute_time forward when called again."""
    debouncer = EnsureJobAfterCooldown(0.1, AsyncMock())
    debouncer.async_schedule()
    first_time = debouncer._next_execute_time
    debouncer.async_schedule()
    assert debouncer._next_execute_time >= first_time
    debouncer._async_cancel_timer()
