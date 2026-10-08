"""Test the roon event entities."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.roon.const import CONF_ROON_ID, DOMAIN
from homeassistant.components.roon.event import RoonEventEntity
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry

ROON_ID = "roon_core"
ENTITY_ID = "event.kitchen_roon_volume"
RENAMED_ENTITY_ID = "event.renamed_volume"
PLAYER_DATA = {
    "dev_id": f"roon_{ROON_ID}_Kitchen",
    "display_name": "Kitchen",
    "source_controls": [{"display_name": "Speaker"}],
}


@pytest.fixture
def mock_roon_api() -> Generator[MagicMock]:
    """Mock the roon api."""
    with patch(
        "homeassistant.components.roon.server.RoonApi", autospec=True
    ) as mock_api:
        yield mock_api.return_value


@pytest.fixture
async def setup_roon_event(
    hass: HomeAssistant, mock_roon_api: MagicMock
) -> AsyncGenerator[None]:
    """Set up roon with only the event platform and add one player."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "token",
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 9330,
            CONF_ROON_ID: ROON_ID,
        },
    )
    entry.add_to_hass(hass)
    with patch("homeassistant.components.roon.PLATFORMS", [Platform.EVENT]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        async_dispatcher_send(hass, "roon_media_player", PLAYER_DATA)
        await hass.async_block_till_done()
        yield
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("setup_roon_event")
async def test_event_entity_id_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_roon_api: MagicMock,
) -> None:
    """Test the event entity is renamed in place and still handles volume events."""
    mock_roon_api.register_volume_control.assert_called_once()
    volume_callback = mock_roon_api.register_volume_control.call_args.args[2]

    with patch.object(
        RoonEventEntity,
        "async_added_to_hass",
        autospec=True,
        side_effect=RoonEventEntity.async_added_to_hass,
    ) as mock_added_to_hass:
        entity_registry.async_update_entity(ENTITY_ID, new_entity_id=RENAMED_ENTITY_ID)
        await hass.async_block_till_done()

    mock_added_to_hass.assert_not_called()
    mock_roon_api.unregister_volume_control.assert_not_called()
    mock_roon_api.register_volume_control.assert_called_once()
    assert hass.states.get(ENTITY_ID) is None
    assert hass.states.get(RENAMED_ENTITY_ID).attributes["event_type"] is None

    volume_callback("control", "set_mute", 0)
    await hass.async_block_till_done()

    assert hass.states.get(RENAMED_ENTITY_ID).attributes["event_type"] == "mute_toggle"
