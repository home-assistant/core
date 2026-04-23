"""Test the Tessie text platform."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.text import DOMAIN as TEXT_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import ERROR_UNKNOWN, assert_entities, setup_platform

NAVIGATION_ENTITY_ID = "text.test_navigation_destination"


async def test_text_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the navigation text entity is set up correctly."""
    entry = await setup_platform(hass, [Platform.TEXT])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_set_navigation_destination(hass: HomeAssistant) -> None:
    """Test sending a navigation destination to the vehicle."""
    await setup_platform(hass, [Platform.TEXT])

    with patch(
        "tesla_fleet_api.tessie.Vehicle.navigation_request",
    ) as mock_nav:
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: NAVIGATION_ENTITY_ID,
                "value": "1 Infinite Loop, Cupertino, CA",
            },
            blocking=True,
        )
        mock_nav.assert_called_once_with("1 Infinite Loop, Cupertino, CA")


async def test_set_navigation_destination_error(hass: HomeAssistant) -> None:
    """Test that a transport error is translated to HomeAssistantError."""
    await setup_platform(hass, [Platform.TEXT])

    with (
        patch(
            "tesla_fleet_api.tessie.Vehicle.navigation_request",
            side_effect=ERROR_UNKNOWN,
        ) as mock_nav,
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: NAVIGATION_ENTITY_ID, "value": "Times Square, New York"},
            blocking=True,
        )

    mock_nav.assert_called_once()
    assert error.value.translation_domain == "tessie"
    assert error.value.translation_key == "cannot_connect"
