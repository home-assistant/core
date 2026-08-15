"""Test the Teslemetry button platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import COMMAND_OK, METADATA

VIN = "LRW3F7EK4NC700000"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_button(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the button entities are correct."""

    entry = await setup_platform(hass, [Platform.BUTTON])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.parametrize(
    ("name", "func"),
    [
        ("wake", "wake_up"),
        ("flash_lights", "flash_lights"),
        ("honk_horn", "honk_horn"),
        ("keyless_driving", "remote_start_drive"),
        ("play_fart", "remote_boombox"),
        ("homelink", "trigger_homelink"),
        ("enable_keep_accessory_power", "set_keep_accessory_power_mode"),
        ("disable_keep_accessory_power", "set_keep_accessory_power_mode"),
    ],
)
async def test_press(hass: HomeAssistant, name: str, func: str) -> None:
    """Test pressing the API buttons."""
    await setup_platform(hass, [Platform.BUTTON])

    with patch(
        f"tesla_fleet_api.teslemetry.Vehicle.{func}",
        return_value=COMMAND_OK,
    ) as command:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: [f"button.test_{name}"]},
            blocking=True,
        )
        command.assert_called_once()


@pytest.mark.parametrize(
    ("firmware", "expected"),
    [
        pytest.param("2025.32", False, id="below_threshold"),
        pytest.param("2025.38", True, id="at_threshold"),
    ],
)
async def test_keep_accessory_power_firmware_gate(
    hass: HomeAssistant,
    mock_metadata: AsyncMock,
    firmware: str,
    expected: bool,
) -> None:
    """Tests that keep accessory power buttons require firmware >= 2025.38."""

    metadata = deepcopy(METADATA)
    metadata["vehicles"][VIN]["firmware"] = firmware
    mock_metadata.return_value = metadata

    await setup_platform(hass, [Platform.BUTTON])

    assert (
        hass.states.get("button.test_enable_keep_accessory_power") is not None
    ) == expected
    assert (
        hass.states.get("button.test_disable_keep_accessory_power") is not None
    ) == expected
