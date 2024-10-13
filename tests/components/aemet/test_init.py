"""Define tests for the AEMET OpenData init."""

from unittest.mock import patch

from aemet_opendata.exceptions import AemetTimeout
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.aemet.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant

from .util import mock_api_call

from tests.common import MockConfigEntry

CONFIG = {
    CONF_NAME: "aemet",
    CONF_API_KEY: "foo",
    CONF_LATITUDE: 40.30403754,
    CONF_LONGITUDE: -3.72935236,
}


async def test_unload_entry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test (un)loading the AEMET integration."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN, unique_id="aemet_unique_id", data=CONFIG
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_init_town_not_found(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test TownNotFound when loading the AEMET integration."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "api-key",
                CONF_LATITUDE: "0.0",
                CONF_LONGITUDE: "0.0",
                CONF_NAME: "AEMET",
            },
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id) is False


async def test_init_api_timeout(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test API timeouts when loading the AEMET integration."""

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=AemetTimeout,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "api-key",
                CONF_LATITUDE: "0.0",
                CONF_LONGITUDE: "0.0",
                CONF_NAME: "AEMET",
            },
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
