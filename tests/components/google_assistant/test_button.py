"""Test buttons."""

from unittest.mock import patch

from pytest import raises

from spencerassistant.components import google_assistant as ga
from spencerassistant.core import Context, spencerAssistant
from spencerassistant.exceptions import spencerAssistantError
from spencerassistant.setup import async_setup_component

from .test_http import DUMMY_CONFIG

from tests.common import MockUser


async def test_sync_button(hass: spencerAssistant, hass_owner_user: MockUser):
    """Test sync button."""

    await async_setup_component(
        hass,
        ga.DOMAIN,
        {"google_assistant": DUMMY_CONFIG},
    )

    await hass.async_block_till_done()

    state = hass.states.get("button.synchronize_devices")
    assert state

    config_entry = hass.config_entries.async_entries("google_assistant")[0]
    google_config: ga.GoogleConfig = hass.data[ga.DOMAIN][config_entry.entry_id]

    with patch.object(google_config, "async_sync_entities") as mock_sync_entities:
        mock_sync_entities.return_value = 200
        context = Context(user_id=hass_owner_user.id)
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.synchronize_devices"},
            blocking=True,
            context=context,
        )
        mock_sync_entities.assert_called_once_with(hass_owner_user.id)

        with raises(spencerAssistantError):
            mock_sync_entities.return_value = 400

            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.synchronize_devices"},
                blocking=True,
                context=context,
            )
