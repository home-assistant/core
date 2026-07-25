"""Test the Tessie button platform."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import ERROR_UNKNOWN, assert_entities, setup_platform


async def test_buttons(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the button entities are correct."""

    entry = await setup_platform(hass, [Platform.BUTTON])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    for entity_id, func in (
        ("button.test_wake", "wake"),
        ("button.test_flash_lights", "flash"),
        ("button.test_honk_horn", "honk"),
        ("button.test_homelink", "tessie_trigger_homelink"),
        ("button.test_keyless_driving", "remote_start"),
        ("button.test_play_fart", "remote_boombox"),
    ):
        with patch(
            f"tesla_fleet_api.tessie.Vehicle.{func}",
        ) as mock_press:
            await hass.services.async_call(
                BUTTON_DOMAIN,
                SERVICE_PRESS,
                {ATTR_ENTITY_ID: [entity_id]},
                blocking=True,
            )
            mock_press.assert_called_once()


async def test_button_error(hass: HomeAssistant) -> None:
    """Test button transport errors are translated."""

    await setup_platform(hass, [Platform.BUTTON])

    with (
        patch(
            "tesla_fleet_api.tessie.Vehicle.wake",
            side_effect=ERROR_UNKNOWN,
        ) as mock_press,
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ["button.test_wake"]},
            blocking=True,
        )

    mock_press.assert_called_once()
    assert error.value.__cause__ == ERROR_UNKNOWN
    assert error.value.translation_domain == "tessie"
    assert error.value.translation_key == "cannot_connect"
