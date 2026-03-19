"""Test the GoodWe initialization."""

from unittest.mock import MagicMock

from homeassistant.components.goodwe import CONF_MODEL_FAMILY, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import TEST_HOST, TEST_PORT

from tests.common import MockConfigEntry


async def test_migration(
    hass: HomeAssistant,
    mock_inverter: MagicMock,
) -> None:
    """Test config entry migration."""

    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_MODEL_FAMILY: "MagicMock",
        },
        entry_id="3bd2acb0e4f0476d40865546d0d91921",
    )
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})

    assert config_entry.version == 2
    assert config_entry.data[CONF_HOST] == TEST_HOST
    assert config_entry.data[CONF_MODEL_FAMILY] == "MagicMock"
    assert config_entry.data[CONF_PORT] == TEST_PORT
