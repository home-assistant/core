"""Test the Netis Router button platform (reboot)."""

from __future__ import annotations

import pytest

from homeassistant.components.netis.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")

ENTRY_ID = "1"


async def test_reboot_button_press(
    hass: HomeAssistant, mock_netis_client
) -> None:
    """Pressing the reboot button should call client.reboot()."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "button", DOMAIN, f"{ENTRY_ID}-reboot"
    )
    assert entity_id is not None
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id},
        blocking=True,
    )
    mock_netis_client.reboot.assert_awaited_once()
