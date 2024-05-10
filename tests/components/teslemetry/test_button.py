"""Test the Teslemetry button platform."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import COMMAND_OK


async def test_button(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the climate entity is correct."""

    entry = await setup_platform(hass, [Platform.BUTTON])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.parametrize(
    ("entity", "func"),
    [
        ("button.test_wake", False),
        ("button.test_flash_lights", "flash_lights"),
        ("button.test_honk", "honk_horn"),
        ("button.test_enable_keyless_driving", "remote_start_drive"),
        ("button.test_boombox", "remote_boombox"),
        ("button.test_homelink", "trigger_homelink"),
        ("button.test_refresh", False),
    ],
)
async def test_press(hass: HomeAssistant, entity: str, func: str) -> None:
    """Test pressing all the buttons"""
    await setup_platform(hass, [Platform.BUTTON])

    if func:
        with patch(
            f"tesla_fleet_api.VehicleSpecific.{func}", side_effect=COMMAND_OK
        ) as command:
            await hass.services.async_call(
                BUTTON_DOMAIN,
                SERVICE_PRESS,
                {ATTR_ENTITY_ID: [entity]},
                blocking=True,
            )
            assert command.assert_called_once()
    else:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: [entity]},
            blocking=True,
        )
