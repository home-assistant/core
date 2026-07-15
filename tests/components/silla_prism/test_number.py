"""Test the Silla Prism number entities."""

from unittest.mock import patch

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

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import MqttMockHAClient

_ENTITY_ID = "number.silla_prism_charging_current"


async def test_number(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the charging-current number entity."""
    with patch("homeassistant.components.silla_prism.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_current(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the charging current publishes the command."""
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: _ENTITY_ID, ATTR_VALUE: 16},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_any_call(
        "prism/1/command/set_current_user", "16", 0, False, message_expiry_interval=None
    )
