"""Tests for the LocknAlert MQTT diagnostics."""

import pytest

from homeassistant.components.locknalert_mqtt.const import (
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import MqttMockHAClientGenerator


@pytest.fixture
def mqtt_config_entry_data() -> dict:
    """Provide config entry data including credentials."""
    return {
        CONF_BROKER: "mock-broker",
        CONF_USERNAME: "mqtt_user",
        CONF_PASSWORD: "super_secret",
    }


@pytest.fixture
def mqtt_config_entry_options() -> dict:
    """Provide config entry options."""
    return {CONF_BIRTH_MESSAGE: {}}


async def test_entry_diagnostics_redacts_credentials(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    hass_client,
) -> None:
    """Config entry diagnostics redact password and username."""
    await mqtt_mock_entry()
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert "connected" in diag
    assert "mqtt_config" in diag

    config_data = diag["mqtt_config"]["data"]
    assert config_data.get(CONF_PASSWORD) == "**REDACTED**"
    assert config_data.get(CONF_USERNAME) == "**REDACTED**"
    assert config_data.get(CONF_BROKER) == "mock-broker"


async def test_entry_diagnostics_includes_devices_list(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    hass_client,
) -> None:
    """Config entry diagnostics includes a devices list."""
    await mqtt_mock_entry()
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert "devices" in diag
    assert isinstance(diag["devices"], list)


async def test_device_diagnostics(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    hass_client,
    device_registry,
) -> None:
    """Device diagnostics return device-specific info."""
    await mqtt_mock_entry()
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "test-device-serial")},
        name="Test Bridge Device",
    )

    diag = await get_diagnostics_for_device(hass, hass_client, entry, device)

    assert "connected" in diag
    assert "device" in diag
    assert diag["device"]["name"] == "Test Bridge Device"
