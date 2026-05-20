"""Tests for the LocknAlert MQTT integration __init__."""

from unittest.mock import patch

import pytest

from homeassistant.components.locknalert_mqtt.const import (
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClientGenerator


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

    with patch(
        "homeassistant.components.locknalert_mqtt.client.AsyncMQTTClient"
    ) as mock_client:
        mock_client.return_value.connect.side_effect = OSError("unreachable")
        # Integration uses early exit — setup should not raise
        result = await hass.config_entries.async_setup(entry.entry_id)
        assert result is True
