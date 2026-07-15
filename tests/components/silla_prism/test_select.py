"""Test the Silla Prism select entities."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import fire_burst, setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import MqttMockHAClient

_ENTITY_ID = "select.silla_prism_charging_mode"


async def test_select(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the charging-mode select entity."""
    with patch("homeassistant.components.silla_prism.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_mode(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting a mode publishes the command."""
    await setup_integration(hass, mock_config_entry)
    await fire_burst(hass)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: _ENTITY_ID, ATTR_OPTION: "solar"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_any_call(
        "prism/1/command/set_mode", "1", 0, False, message_expiry_interval=None
    )
