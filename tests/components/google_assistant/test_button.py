"""Test buttons."""

from unittest.mock import patch

import pytest

from homeassistant.components import google_assistant as ga
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .test_http import DUMMY_CONFIG

from tests.common import MockUser


async def test_sync_button(hass: HomeAssistant, hass_owner_user: MockUser) -> None:
    """Test sync button."""

    await async_setup_component(
        hass,
        ga.DOMAIN,
        {"google_assistant": DUMMY_CONFIG},
    )

    await hass.async_block_till_done()

    state = hass.states.get("button.google_assistant_synchronize_devices")
    assert state

    config_entry = hass.config_entries.async_entries("google_assistant")[0]
    google_config: ga.GoogleConfig = hass.data[ga.DOMAIN][config_entry.entry_id]

    with patch.object(google_config, "async_sync_entities") as mock_sync_entities:
        mock_sync_entities.return_value = 200
        context = Context(user_id=hass_owner_user.id)
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.google_assistant_synchronize_devices"},
            blocking=True,
            context=context,
        )
        mock_sync_entities.assert_called_once_with(hass_owner_user.id)

        with pytest.raises(HomeAssistantError):
            mock_sync_entities.return_value = 400

            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.google_assistant_synchronize_devices"},
                blocking=True,
                context=context,
            )
