"""Test the Tesla Fleet button platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from syrupy import SnapshotAssertion
from tesla_fleet_api.exceptions import NotOnWhitelistFault

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
        f"tesla_fleet_api.tesla.VehicleFleet.{func}",
        return_value=COMMAND_OK,
    ) as command:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: [f"button.test_{name}"]},
            blocking=True,
        )
        command.assert_called_once()


async def test_press_signing_error(
    hass: HomeAssistant, normal_config_entry: MockConfigEntry, mock_products: AsyncMock
) -> None:
    """Test pressing a button with a signing error."""
    # Enable Signing
    new_product = deepcopy(mock_products.return_value)
    new_product["response"][0]["command_signing"] = "required"
    mock_products.return_value = new_product

    with (
        patch("homeassistant.components.tesla_fleet.TeslaFleetApi.get_private_key"),
    ):
        await setup_platform(hass, normal_config_entry, [Platform.BUTTON])

    with (
        patch("homeassistant.components.tesla_fleet.TeslaFleetApi.get_private_key"),
        patch(
            "tesla_fleet_api.tesla.VehicleSigned.flash_lights",
            side_effect=NotOnWhitelistFault,
        ),
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ["button.test_flash_lights"]},
            blocking=True,
        )
    assert error.from_exception(NotOnWhitelistFault)
