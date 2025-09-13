"""Tests for TTS media source."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from radios import FilterBy, Order

from homeassistant.components import media_source
from homeassistant.components.radio_browser.media_source import async_get_media_source
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

DOMAIN = "radio_browser"


@pytest.fixture(autouse=True)
async def setup_media_source(hass: HomeAssistant) -> None:
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})


class DummyCountry:
    """Country Object for Radios."""

    def __init__(self, code, name) -> None:
        """Initialize a dummy country."""
        self.code = code
        self.name = name
        self.favicon = "fake.png"


class DummyStation:
    """Station object for Radios."""

    def __init__(self, country_code, latitude, longitude, name, uuid) -> None:
        """Initialize a dummy station."""
        self.country_code = country_code
        self.latitude = latitude
        self.longitude = longitude
        self.uuid = uuid
        self.name = name
        self.codec = "MP3"
        self.favicon = "fake.png"


async def test_browsing_local(hass: HomeAssistant, init_integration: AsyncMock) -> None:
    """Test browsing radio_browser local stations."""

    hass.config.latitude = 45.58539
    hass.config.longitude = -122.40320
    hass.config.country = "US"

    dummy_radios = MagicMock()
    dummy_radios.countries = AsyncMock(
        return_value=[DummyCountry("US", "United States")]
    )

    dummy_radios.stations = AsyncMock(
        return_value=[
            DummyStation(
                country_code="US",
                latitude=45.52000,
                longitude=-122.63961,
                name="Near Station 1",
                uuid="1",
            ),
            DummyStation(
                country_code="US",
                latitude=None,
                longitude=None,
                name="Unknown location station",
                uuid="2",
            ),
            DummyStation(
                country_code="US",
                latitude=47.57071,
                longitude=-122.21148,
                name="Moderate Far Station",
                uuid="3",
            ),
            DummyStation(
                country_code="US",
                latitude=45.73943,
                longitude=-121.51859,
                name="Near Station 2",
                uuid="4",
            ),
            DummyStation(
                country_code="US",
                latitude=44.99026,
                longitude=-69.27804,
                name="Really Far Station",
                uuid="5",
            ),
        ]
    )

    source = await async_get_media_source(hass)

    with patch.object(type(source), "radios", new_callable=PropertyMock) as mock_radios:
        mock_radios.return_value = dummy_radios
        assert source.radios is dummy_radios

        item = await media_source.async_browse_media(
            hass, f"{media_source.URI_SCHEME}{DOMAIN}"
        )

        assert item is not None
        assert item.title == "My Radios"
        assert item.children is not None
        assert len(item.children) == 5
        assert item.can_play is False
        assert item.can_expand is True

        assert item.children[3].title == "Local stations"

        item_child = await media_source.async_browse_media(
            hass, item.children[3].media_content_id
        )

        dummy_radios.stations.assert_awaited_with(
            filter_by=FilterBy.COUNTRY_CODE_EXACT,
            filter_term=hass.config.country,
            hide_broken=True,
            order=Order.NAME,
            reverse=False,
        )

        assert item_child is not None
        assert item_child.title == "My Radios"
        assert len(item_child.children) == 2
        assert item_child.children[0].title == "Near Station 1"
        assert item_child.children[1].title == "Near Station 2"

        # Test browsing a different category to hit the path where async_build_local
        # returns []
        other_browse = await media_source.async_browse_media(
            hass, f"{media_source.URI_SCHEME}{DOMAIN}/nonexistent"
        )

        assert other_browse is not None
        assert other_browse.title == "My Radios"
        assert len(other_browse.children) == 0
