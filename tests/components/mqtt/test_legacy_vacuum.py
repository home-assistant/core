"""The tests for the Legacy Mqtt vacuum platform."""

# The legacy schema for MQTT vacuum was deprecated with HA Core 2023.8.0
# and was removed with HA Core 2024.2.0
# cleanup is planned with HA Core 2025.2

import json

import pytest

from homeassistant.components import mqtt, vacuum
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import DiscoveryInfoType

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClientGenerator

DEFAULT_CONFIG = {mqtt.DOMAIN: {vacuum.DOMAIN: {"name": "test"}}}


@pytest.mark.parametrize(
    ("hass_config", "removed"),
    [
        ({mqtt.DOMAIN: {vacuum.DOMAIN: {"name": "test", "schema": "legacy"}}}, True),
        ({mqtt.DOMAIN: {vacuum.DOMAIN: {"name": "test"}}}, False),
        ({mqtt.DOMAIN: {vacuum.DOMAIN: {"name": "test", "schema": "state"}}}, False),
    ],
)
async def test_removed_support_yaml(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    removed: bool,
) -> None:
    """Test that the removed support validation for the legacy schema works."""
    assert await mqtt_mock_entry()
    entity = hass.states.get("vacuum.test")

    if removed:
        assert entity is None
        assert (
            "The support for the `legacy` MQTT "
            "vacuum schema has been removed" in caplog.text
        )
    else:
        assert entity is not None


@pytest.mark.parametrize(
    ("config", "removed"),
    [
        ({"name": "test", "schema": "legacy"}, True),
        ({"name": "test"}, False),
        ({"name": "test", "schema": "state"}, False),
    ],
)
async def test_removed_support_discovery(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    config: DiscoveryInfoType,
    removed: bool,
) -> None:
    """Test that the removed support validation for the legacy schema works."""
    assert await mqtt_mock_entry()

    config_payload = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/vacuum/test/config", config_payload)
    await hass.async_block_till_done()

    entity = hass.states.get("vacuum.test")

    if removed:
        assert entity is None
        assert (
            "The support for the `legacy` MQTT "
            "vacuum schema has been removed" in caplog.text
        )
    else:
        assert entity is not None
