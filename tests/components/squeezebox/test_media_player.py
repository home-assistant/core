"""Test squeezebox media player."""

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import FAKE_QUERY_RESPONSE, setup_mocked_integration


async def test_media_player(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor states and attributes."""

    # Setup component
    with (
        patch(
            "homeassistant.components.squeezebox.PLATFORMS",
            [Platform.MEDIA_PLAYER],
        ),
        patch(
            "pysqueezebox.Server.async_query",
            return_value=FAKE_QUERY_RESPONSE,
        ),
    ):
        await setup_mocked_integration(hass)
