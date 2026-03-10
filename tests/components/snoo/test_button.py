"""Test Snoo Buttons."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

from tests.common import snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    bypass_api: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test buttons."""
    with patch("homeassistant.components.snoo.PLATFORMS", [Platform.BUTTON]):
        entry = await async_init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_button_starts_snoo(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test start_snoo button works correctly."""
    await async_init_integration(hass)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_snoo_start"},
        blocking=True,
    )

    assert bypass_api.start_snoo.assert_called_once
