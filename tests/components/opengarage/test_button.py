"""Test the OpenGarage Browser buttons."""
from unittest.mock import MagicMock

import homeassistant.components.button as button
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_buttons(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test standard OpenGarage buttons."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    entry = entity_registry.async_get("button.abcdef_reboot_device")
    assert entry
    assert entry.unique_id == "abcdef-reboot_device"
    await hass.services.async_call(
        button.DOMAIN,
        button.SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.abcdef_reboot_device"},
        blocking=True,
    )
    assert len(mock_opengarage.reboot.mock_calls) == 1

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
