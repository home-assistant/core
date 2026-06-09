"""Tests for the LocknAlert MQTT integration __init__."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.locknalert_mqtt import (
    SERVICE_PUBLISH,
    async_check_config_schema,
    async_remove_config_entry_device,
    async_setup as locknalert_async_setup,
    async_subscribe_connection_status,
    discovery as mqtt_discovery,
    is_connected,
)
from homeassistant.components.locknalert_mqtt.const import (
    ATTR_TOPIC,
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONF_DISCOVERY,
    CONF_DISCOVERY_PREFIX,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
    MQTT_CONNECTION_STATE,
)
from homeassistant.components.locknalert_mqtt.models import DATA_MQTT
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigValidationError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient


@pytest.fixture
def mqtt_config_entry_data() -> dict:
    """Provide default config entry data."""
    return {CONF_BROKER: "mock-broker"}


@pytest.fixture
def mqtt_config_entry_options() -> dict:
    """Provide default config entry options."""
    return {CONF_BIRTH_MESSAGE: {}}


async def test_setup_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Integration sets up without errors and is marked as loaded."""
    await mqtt_mock_entry()
    assert DOMAIN in hass.config.components


async def test_unload_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Integration unloads cleanly."""
    await mqtt_mock_entry()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state.value == "not_loaded"


async def test_publish_service_is_registered(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """The locknalert_mqtt.publish service is registered after setup."""
    await mqtt_mock_entry()
    assert hass.services.has_service(DOMAIN, "publish")


async def test_reload_service_is_registered(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """The locknalert_mqtt.reload service is registered after setup."""
    await mqtt_mock_entry()
    assert hass.services.has_service(DOMAIN, "reload")


async def test_dump_service_is_registered(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """The locknalert_mqtt.dump service is registered after setup."""
    await mqtt_mock_entry()
    assert hass.services.has_service(DOMAIN, "dump")


async def test_setup_entry_fails_if_broker_unreachable(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Setup succeeds even when the broker is not yet reachable (early exit)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_BROKER: "unreachable-broker"},
        options={CONF_BIRTH_MESSAGE: {}},
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)
    mqtt_client_mock.connect.side_effect = OSError("unreachable")
    result = await hass.config_entries.async_setup(entry.entry_id)
    assert result is True
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# async_migrate_entry
# ---------------------------------------------------------------------------


async def test_migrate_entry_future_version_returns_false(
    hass: HomeAssistant,
) -> None:
    """Setup fails for entries from a future major version (migration returns False)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_BROKER: "mock-broker"},
        options={},
        version=3,
        minor_version=0,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(entry.entry_id)
    assert result is False


async def test_migrate_entry_v2_future_minor_returns_false(
    hass: HomeAssistant,
) -> None:
    """Setup fails for v2 entries with an unrecognised minor version."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_BROKER: "mock-broker"},
        options={},
        version=2,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(entry.entry_id)
    assert result is False


async def test_migrate_entry_v1_0_moves_option_fields(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Migration moves ENTRY_OPTION_FIELDS from data to options for v1.0 entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BROKER: "mock-broker",
            CONF_DISCOVERY: True,
            CONF_DISCOVERY_PREFIX: "homeassistant",
            "birth_message": {},
            "will_message": {},
        },
        options={},
        version=1,
        minor_version=0,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert result is True
    assert CONF_DISCOVERY not in entry.data
    assert CONF_DISCOVERY in entry.options
    assert "birth_message" not in entry.data
    assert "birth_message" in entry.options
    assert entry.version == 1
    assert entry.minor_version == 2


async def test_migrate_entry_v1_2_noop_returns_true(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Setup succeeds without changes for an already-migrated v1.2 entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_BROKER: "mock-broker"},
        options={CONF_DISCOVERY: True},
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert result is True
    assert entry.minor_version == 2


# ---------------------------------------------------------------------------
# is_connected
# ---------------------------------------------------------------------------


async def test_is_connected_returns_true_when_connected(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """is_connected returns True when the MQTT client reports it is connected."""
    await mqtt_mock_entry()
    assert is_connected(hass) is True


# ---------------------------------------------------------------------------
# async_subscribe_connection_status
# ---------------------------------------------------------------------------


async def test_async_subscribe_connection_status_invokes_callback(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """async_subscribe_connection_status invokes callback when MQTT_CONNECTION_STATE dispatched."""
    await mqtt_mock_entry()
    received: list[bool] = []

    def connection_callback(connected: bool) -> None:
        received.append(connected)

    unsub = async_subscribe_connection_status(hass, connection_callback)
    assert callable(unsub)
    async_dispatcher_send(hass, MQTT_CONNECTION_STATE, False)
    await hass.async_block_till_done()
    assert received == [False]
    unsub()


# ---------------------------------------------------------------------------
# async_remove_config_entry_device
# ---------------------------------------------------------------------------


async def test_async_remove_config_entry_device_returns_true(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """async_remove_config_entry_device always returns True."""
    await mqtt_mock_entry()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device_entry = MagicMock()
    result = await async_remove_config_entry_device(hass, entry, device_entry)
    assert result is True


# ---------------------------------------------------------------------------
# async_publish_service: evaluate_payload
# ---------------------------------------------------------------------------


async def test_publish_service_evaluate_payload_converts_bytes_literal(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Publish service with evaluate_payload=True converts a bytes-literal payload to bytes."""
    mqtt_mock = await mqtt_mock_entry()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PUBLISH,
        {
            ATTR_TOPIC: "test/topic",
            "payload": "b'hello'",
            "evaluate_payload": True,
        },
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once()
    call_args = mqtt_mock.async_publish.call_args[0]
    assert call_args[1] == b"hello"


# ---------------------------------------------------------------------------
# async_publish_service: not configured
# ---------------------------------------------------------------------------


async def test_publish_service_raises_when_not_configured(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Publish service raises ServiceValidationError when MQTT is not configured."""
    await mqtt_mock_entry()
    with (
        patch(
            "homeassistant.components.locknalert_mqtt.mqtt_config_entry_enabled",
            return_value=False,
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PUBLISH,
            {ATTR_TOPIC: "test/topic", "payload": "payload"},
            blocking=True,
        )


# ---------------------------------------------------------------------------
# async_setup: yaml without active entry creates issue
# ---------------------------------------------------------------------------


async def test_async_setup_yaml_without_entry_creates_issue(
    hass: HomeAssistant,
) -> None:
    """async_setup creates yaml_setup_without_active_setup issue when yaml present but no active entry."""
    with patch(
        "homeassistant.components.locknalert_mqtt.mqtt_config_entry_enabled",
        return_value=False,
    ):
        result = await locknalert_async_setup(hass, {DOMAIN: {}})

    assert result is True
    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue(DOMAIN, "yaml_setup_without_active_setup")
    assert issue is not None


# ---------------------------------------------------------------------------
# _reload_config: ConfigValidationError is re-raised as ServiceValidationError
# ---------------------------------------------------------------------------


async def test_reload_service_raises_service_validation_error_on_bad_config(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Reload service raises ServiceValidationError when config YAML has errors."""
    await mqtt_mock_entry()
    bad_exc = ConfigValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_platform_config",
        translation_placeholders={"domain": "alarm_control_panel"},
    )
    with (
        patch(
            "homeassistant.components.locknalert_mqtt.async_integration_yaml_config",
            new_callable=AsyncMock,
            side_effect=bad_exc,
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, {}, blocking=True)


# ---------------------------------------------------------------------------
# async_setup_entry: subscriptions are restored after reload
# ---------------------------------------------------------------------------


async def test_setup_entry_restores_subscriptions_on_reload(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Subscriptions saved during unload are restored when the entry is set up again."""
    await mqtt_mock_entry()
    mqtt_data = hass.data[DATA_MQTT]
    fake_sub = MagicMock()
    mqtt_data.subscriptions_to_restore = {fake_sub}

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    restored_mqtt_data = hass.data[DATA_MQTT]
    restored_mqtt_data.client.async_restore_tracked_subscriptions.assert_called()


# ---------------------------------------------------------------------------
# async_check_config_schema
# ---------------------------------------------------------------------------


async def test_async_check_config_schema_valid(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """async_check_config_schema passes silently for a valid YAML config."""
    await mqtt_mock_entry()
    # Empty config is always valid — no items to validate.
    await async_check_config_schema(hass, {DOMAIN: []})


async def test_async_check_config_schema_invalid_raises(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """async_check_config_schema raises ServiceValidationError for a bad item."""
    await mqtt_mock_entry()
    mqtt_data = hass.data[DATA_MQTT]

    # Register a schema that rejects everything.
    mqtt_data.reload_schema["alarm_control_panel"] = vol.Schema(
        vol.Invalid("always bad")
    )

    with pytest.raises(ServiceValidationError):
        await async_check_config_schema(
            hass,
            {DOMAIN: [{"alarm_control_panel": [{"name": "bad"}]}]},
        )


# ---------------------------------------------------------------------------
# SERVICE_DUMP
# ---------------------------------------------------------------------------


async def test_dump_service_is_callable(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Dump service can be called without raising an exception."""
    await mqtt_mock_entry()
    with patch("homeassistant.components.locknalert_mqtt.ev.async_call_later"):
        await hass.services.async_call(
            DOMAIN,
            "dump",
            {"topic": "test/topic", "duration": 1},
            blocking=True,
        )


# ---------------------------------------------------------------------------
# async_publish_service: plain payload (no evaluate_payload)
# ---------------------------------------------------------------------------


async def test_publish_service_plain_payload(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Publish service sends a plain string payload without conversion."""
    mqtt_mock = await mqtt_mock_entry()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PUBLISH,
        {ATTR_TOPIC: "test/plain", "payload": "hello"},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once()
    call_args = mqtt_mock.async_publish.call_args[0]
    assert call_args[1] == "hello"


async def test_publish_service_evaluate_payload_plain_string(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Publish with evaluate_payload=True and a non-bytes literal passes the string through."""
    mqtt_mock = await mqtt_mock_entry()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PUBLISH,
        {
            ATTR_TOPIC: "test/topic",
            "payload": "plain-string",
            "evaluate_payload": True,
        },
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once()
    call_args = mqtt_mock.async_publish.call_args[0]
    # Non-bytes-literal strings pass through as-is.
    assert call_args[1] == "plain-string"


# ---------------------------------------------------------------------------
# async_setup: no yaml config → no issue created
# ---------------------------------------------------------------------------


async def test_async_setup_no_yaml_no_issue(
    hass: HomeAssistant,
) -> None:
    """async_setup does NOT create an issue when no yaml config is present."""
    with patch(
        "homeassistant.components.locknalert_mqtt.mqtt_config_entry_enabled",
        return_value=False,
    ):
        result = await locknalert_async_setup(hass, {})

    assert result is True
    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue(DOMAIN, "yaml_setup_without_active_setup")
    assert issue is None


# ---------------------------------------------------------------------------
# async_setup_entry: discovery disabled
# ---------------------------------------------------------------------------


async def test_setup_entry_discovery_disabled(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mqtt_config_entry_options: dict,
) -> None:
    """When discovery=False in options, async_start is not called."""
    with patch.object(mqtt_discovery, "async_start") as mock_start:
        mqtt_config_entry_options[CONF_DISCOVERY] = False
        await mqtt_mock_entry()
        mock_start.assert_not_called()


# ---------------------------------------------------------------------------
# async_unload_entry: subscriptions are preserved
# ---------------------------------------------------------------------------


async def test_unload_entry_preserves_subscriptions(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """When client has subscriptions at unload, they are saved to subscriptions_to_restore."""
    await mqtt_mock_entry()
    mqtt_data = hass.data[DATA_MQTT]
    fake_sub = MagicMock()
    mqtt_data.client.subscriptions = {fake_sub}

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert fake_sub in mqtt_data.subscriptions_to_restore


# ---------------------------------------------------------------------------
# _async_remove_mqtt_issues
# ---------------------------------------------------------------------------


async def test_reload_removes_invalid_platform_config_issues(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Reload service removes open invalid_platform_config repair issues."""
    await mqtt_mock_entry()
    ir.async_create_issue(
        hass,
        DOMAIN,
        "stale_issue_id",
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="invalid_platform_config",
        translation_placeholders={"domain": "alarm_control_panel"},
    )
    issue_reg = ir.async_get(hass)
    assert issue_reg.async_get_issue(DOMAIN, "stale_issue_id") is not None

    with patch(
        "homeassistant.components.locknalert_mqtt.async_integration_yaml_config",
        new_callable=AsyncMock,
        return_value={DOMAIN: []},
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, {}, blocking=True)

    assert issue_reg.async_get_issue(DOMAIN, "stale_issue_id") is None
