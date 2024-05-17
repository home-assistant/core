"""Test the OpenGarage Browser buttons."""

from unittest.mock import MagicMock

from homeassistant.components import button
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_buttons(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test standard OpenGarage buttons."""
    entry = entity_registry.async_get("button.abcdef_restart")
    assert entry
    assert entry.unique_id == "12345_restart"
    await hass.services.async_call(
        button.DOMAIN,
        button.SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.abcdef_restart"},
        blocking=True,
    )
    assert len(mock_opengarage.reboot.mock_calls) == 1

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
