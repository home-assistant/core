"""Tests for Sonos services."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN, SERVICE_JOIN
from homeassistant.components.sonos.const import DATA_SONOS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_media_player_join(hass: HomeAssistant, async_autosetup_sonos) -> None:
    """Test join service."""
    valid_entity_id = "media_player.zone_a"
    mocked_entity_id = "media_player.mocked"

    # Ensure an error is raised if the entity is unknown
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_JOIN,
            {"entity_id": valid_entity_id, "group_members": mocked_entity_id},
            blocking=True,
        )

    # Ensure SonosSpeaker.join_multi is called if entity is found
    mocked_speaker = Mock()
    mock_entity_id_mappings = {mocked_entity_id: mocked_speaker}

    with patch.dict(
        hass.data[DATA_SONOS].entity_id_mappings, mock_entity_id_mappings
    ), patch(
        "homeassistant.components.sonos.speaker.SonosSpeaker.join_multi"
    ) as mock_join_multi:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_JOIN,
            {"entity_id": valid_entity_id, "group_members": mocked_entity_id},
            blocking=True,
        )

        found_speaker = hass.data[DATA_SONOS].entity_id_mappings[valid_entity_id]
        mock_join_multi.assert_called_with(hass, found_speaker, [mocked_speaker])
