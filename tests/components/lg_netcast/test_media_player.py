"""Tests for LG Netcast media player platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET

import pytest

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import MODEL_NAME, setup_lgnetcast

from tests.common import async_fire_time_changed

ENTITY_ID = f"{MP_DOMAIN}.{MODEL_NAME.lower()}"


def _make_channel(name: str, major: str) -> ET.Element:
    """Create a fake channel XML element."""
    channel = ET.Element("data")
    chname = ET.SubElement(channel, "chname")
    chname.text = name
    major_el = ET.SubElement(channel, "major")
    major_el.text = major
    return channel


@pytest.fixture(autouse=True)
def mock_lg_netcast() -> Generator[MagicMock]:
    """Mock LG Netcast library."""
    with patch(
        "homeassistant.components.lg_netcast.LgNetCastClient"
    ) as mock_client_class:
        yield mock_client_class


async def test_source_list_duplicate_channel_names(
    hass: HomeAssistant,
    mock_lg_netcast: MagicMock,
) -> None:
    """Test that duplicate channel names are disambiguated in source list."""
    client = mock_lg_netcast.return_value
    client.get_volume.return_value = (20, False)
    context_client = client.__enter__.return_value
    channel_data = {
        "cur_channel": None,
        "channel_list": [
            _make_channel("BBC One", "1"),
            _make_channel("ITV", "3"),
            _make_channel("BBC One", "101"),
        ],
    }
    context_client.query_data.side_effect = channel_data.get

    await setup_lgnetcast(hass)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(ENTITY_ID)
    assert entity is not None
    source_list = entity.attributes.get("source_list")
    assert source_list is not None
    assert len(source_list) == 3
    assert "ITV" in source_list
    assert "BBC One (1)" in source_list
    assert "BBC One (101)" in source_list
