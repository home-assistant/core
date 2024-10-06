"""Test the Tesla Fleet button platform."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import COMMAND_OK

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_button(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the button entities are correct."""

    await setup_platform(hass, normal_config_entry, [Platform.BUTTON])
    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: ["button.test_wake"]},
        blocking=True,
    )


@pytest.mark.parametrize(
    ("name", "func"),
    [
        ("flash_lights", "flash_lights"),
        ("honk_horn", "honk_horn"),
        ("keyless_driving", "remote_start_drive"),
        ("play_fart", "remote_boombox"),
        ("homelink", "trigger_homelink"),
    ],
)
async def test_press(
    hass: HomeAssistant, normal_config_entry: MockConfigEntry, name: str, func: str
) -> None:
    """Test pressing the API buttons."""
    await setup_platform(hass, normal_config_entry, [Platform.BUTTON])

    with patch(
        f"homeassistant.components.tesla_fleet.VehicleSpecific.{func}",
        return_value=COMMAND_OK,
    ) as command:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: [f"button.test_{name}"]},
            blocking=True,
        )
        command.assert_called_once()
