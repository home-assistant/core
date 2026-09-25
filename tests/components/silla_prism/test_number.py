"""Test the Silla Prism numbers."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import fire_burst, setup_integration

from tests.common import MockConfigEntry, async_fire_mqtt_message, snapshot_platform
from tests.typing import MqttMockHAClient

USER_CURRENT_ENTITY_ID = "number.silla_prism_maximum_charging_current"
USER_AMP_TOPIC = "prism/1/user_amp"
SET_CURRENT_USER_TOPIC = "prism/1/command/set_current_user"


async def test_numbers(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the numbers."""
    await setup_integration(hass, mock_config_entry, [Platform.NUMBER])
    await fire_burst(hass)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_user_current(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that setting the current publishes the matching command."""
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: USER_CURRENT_ENTITY_ID, ATTR_VALUE: 16},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        SET_CURRENT_USER_TOPIC, "16", 0, False, message_expiry_interval=None
    )


@pytest.mark.usefixtures("mqtt_mock")
async def test_user_current_updates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the current follows the one reported by Prism."""
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    assert hass.states.get(USER_CURRENT_ENTITY_ID).state == "6"

    async_fire_mqtt_message(hass, USER_AMP_TOPIC, "20")
    await hass.async_block_till_done()

    assert hass.states.get(USER_CURRENT_ENTITY_ID).state == "20"
