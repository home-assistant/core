"""Tests for the LocknAlert MQTT integration __init__."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components import alarm_control_panel
from homeassistant.components.locknalert_mqtt import (
    SERVICE_PUBLISH,
    async_migrate_entry,
    async_remove_config_entry_device,
    async_subscribe_connection_status,
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
from homeassistant.const import CONF_DISCOVERY as HA_CONF_DISCOVERY, SERVICE_RELOAD
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
    """async_migrate_entry returns False for entries from a future version."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_BROKER: "mock-broker"},
        options={},
        version=3,
        minor_version=0,
    )
    entry.add_to_hass(hass)
    result = await async_migrate_entry(hass, entry)
    assert result is False


async def test_migrate_entry_v2_future_minor_returns_false(
    hass: HomeAssistant,
) -> None:
    """async_migrate_entry returns False for v2 entries with future minor version."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_BROKER: "mock-broker"},
        options={},
        version=2,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    result = await async_migrate_entry(hass, entry)
    assert result is False


async def test_migrate_entry_v1_0_moves_option_fields(
    hass: HomeAssistant,
) -> None:
    """async_migrate_entry migrates ENTRY_OPTION_FIELDS from data to options for v1.0 entries."""
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
    result = await async_migrate_entry(hass, entry)
    assert result is True
    assert CONF_DISCOVERY not in entry.data
    assert CONF_DISCOVERY in entry.options
    assert "birth_message" not in entry.data
    assert "birth_message" in entry.options
    assert entry.version == 1
    assert entry.minor_version == 2


async def test_migrate_entry_v1_2_noop_returns_true(
    hass: HomeAssistant,
) -> None:
    """async_migrate_entry returns True without changes for already-migrated v1.2 entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_BROKER: "mock-broker"},
        options={CONF_DISCOVERY: True},
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    result = await async_migrate_entry(hass, entry)
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
    from homeassistant.components.locknalert_mqtt import (  # noqa: PLC0415
        async_setup as locknalert_async_setup,
    )

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
        await hass.services.async_call(
            DOMAIN, SERVICE_RELOAD, {}, blocking=True
        )


# ---------------------------------------------------------------------------
# async_setup_entry: subscriptions are restored after reload
# ---------------------------------------------------------------------------


async def test_setup_entry_restores_subscriptions_on_reload(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Subscriptions saved during unload are restored when the entry is set up again."""
    await mqtt_mock_entry()
    from homeassistant.components.locknalert_mqtt.models import DATA_MQTT  # noqa: PLC0415

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
