"""Test the Emulated Hue component."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import web

from homeassistant.components.emulated_hue.config import (
    DATA_KEY,
    DATA_VERSION,
    SAVE_DELAY,
    Config,
)
from homeassistant.components.emulated_hue.upnp import UPNPResponderProtocol
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import utcnow

from tests.common import async_fire_time_changed


async def test_config_google_home_entity_id_to_number(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test config adheres to the type."""
    conf = Config(hass, {"type": "google_home"}, "127.0.0.1")
    hass_storage[DATA_KEY] = {
        "version": DATA_VERSION,
        "key": DATA_KEY,
        "data": {"1": "light.test2"},
    }

    await conf.async_setup()

    number = conf.entity_id_to_number("light.test")
    assert number == "2"

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=SAVE_DELAY))
    await hass.async_block_till_done()
    assert hass_storage[DATA_KEY]["data"] == {
        "1": "light.test2",
        "2": "light.test",
    }

    number = conf.entity_id_to_number("light.test")
    assert number == "2"

    number = conf.entity_id_to_number("light.test2")
    assert number == "1"

    entity_id = conf.number_to_entity_id("1")
    assert entity_id == "light.test2"


async def test_config_google_home_entity_id_to_number_altered(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test config adheres to the type."""
    conf = Config(hass, {"type": "google_home"}, "127.0.0.1")
    hass_storage[DATA_KEY] = {
        "version": DATA_VERSION,
        "key": DATA_KEY,
        "data": {"21": "light.test2"},
    }

    await conf.async_setup()

    number = conf.entity_id_to_number("light.test")
    assert number == "22"

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=SAVE_DELAY))
    await hass.async_block_till_done()
    assert hass_storage[DATA_KEY]["data"] == {
        "21": "light.test2",
        "22": "light.test",
    }

    number = conf.entity_id_to_number("light.test")
    assert number == "22"

    number = conf.entity_id_to_number("light.test2")
    assert number == "21"

    entity_id = conf.number_to_entity_id("21")
    assert entity_id == "light.test2"


async def test_config_google_home_entity_id_to_number_empty(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test config adheres to the type."""
    conf = Config(hass, {"type": "google_home"}, "127.0.0.1")
    hass_storage[DATA_KEY] = {"version": DATA_VERSION, "key": DATA_KEY, "data": {}}

    await conf.async_setup()

    number = conf.entity_id_to_number("light.test")
    assert number == "1"

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=SAVE_DELAY))
    await hass.async_block_till_done()
    assert hass_storage[DATA_KEY]["data"] == {"1": "light.test"}

    number = conf.entity_id_to_number("light.test")
    assert number == "1"

    number = conf.entity_id_to_number("light.test2")
    assert number == "2"

    entity_id = conf.number_to_entity_id("2")
    assert entity_id == "light.test2"


def test_config_alexa_entity_id_to_number() -> None:
    """Test config adheres to the type."""
    conf = Config(None, {"type": "alexa"}, "127.0.0.1")

    number = conf.entity_id_to_number("light.test")
    assert number == "light.test"

    number = conf.entity_id_to_number("light.test")
    assert number == "light.test"

    number = conf.entity_id_to_number("light.test2")
    assert number == "light.test2"

    entity_id = conf.number_to_entity_id("light.test")
    assert entity_id == "light.test"


async def test_setup_works(hass: HomeAssistant) -> None:
    """Test setup works."""
    hass.config.components.add("network")
    with (
        patch(
            "homeassistant.components.emulated_hue.async_create_upnp_datagram_endpoint",
            AsyncMock(),
        ) as mock_create_upnp_datagram_endpoint,
        patch("homeassistant.components.emulated_hue.async_get_source_ip"),
        patch(
            "homeassistant.components.emulated_hue.web.TCPSite",
            return_value=Mock(spec_set=web.TCPSite),
        ),
    ):
        mock_create_upnp_datagram_endpoint.return_value = AsyncMock(
            spec=UPNPResponderProtocol
        )
        assert await async_setup_component(hass, "emulated_hue", {})
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_create_upnp_datagram_endpoint.mock_calls) == 1
