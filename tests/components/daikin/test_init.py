"""Define tests for the Daikin init."""
import asyncio
from unittest.mock import AsyncMock, PropertyMock, patch

from aiohttp import ClientConnectionError
import pytest

from homeassistant.components.daikin import update_unique_id
from homeassistant.components.daikin.const import DOMAIN, KEY_MAC
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .test_config_flow import HOST, MAC

from tests.common import MockConfigEntry


@pytest.fixture
def mock_daikin():
    """Mock pydaikin."""

    async def mock_daikin_factory(*args, **kwargs):
        """Mock the init function in pydaikin."""
        return Appliance

    with patch("homeassistant.components.daikin.Appliance") as Appliance:
        Appliance.factory.side_effect = mock_daikin_factory
        type(Appliance).update_status = AsyncMock()
        type(Appliance).inside_temperature = PropertyMock(return_value=22)
        type(Appliance).target_temperature = PropertyMock(return_value=22)
        type(Appliance).zones = PropertyMock(return_value=[("Zone 1", "0", 0)])
        type(Appliance).fan_rate = PropertyMock(return_value=[])
        type(Appliance).swing_modes = PropertyMock(return_value=[])
        yield Appliance


DATA = {
    "ver": "1_1_8",
    "name": "DaikinAP00000",
    "mac": MAC,
    "model": "NOTSUPPORT",
}


INVALID_DATA = {**DATA, "name": None, "mac": HOST}


async def test_unique_id_migrate(hass: HomeAssistant, mock_daikin) -> None:
    """Test unique id migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        title=None,
        data={CONF_HOST: HOST, KEY_MAC: HOST},
    )
    config_entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    type(mock_daikin).mac = PropertyMock(return_value=HOST)
    type(mock_daikin).values = PropertyMock(return_value=INVALID_DATA)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.unique_id == HOST

    assert device_registry.async_get_device(connections={(KEY_MAC, HOST)}).name is None

    entity = entity_registry.async_get("climate.daikin_127_0_0_1")
    assert entity.unique_id == HOST
    assert update_unique_id(entity, MAC) is not None

    assert entity_registry.async_get("switch.none_zone_1").unique_id.startswith(HOST)

    type(mock_daikin).mac = PropertyMock(return_value=MAC)
    type(mock_daikin).values = PropertyMock(return_value=DATA)

    assert config_entry.unique_id != MAC

    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.unique_id == MAC

    assert (
        device_registry.async_get_device(connections={(KEY_MAC, MAC)}).name
        == "DaikinAP00000"
    )

    entity = entity_registry.async_get("climate.daikin_127_0_0_1")
    assert entity.unique_id == MAC
    assert update_unique_id(entity, MAC) is None

    assert entity_registry.async_get("switch.none_zone_1").unique_id.startswith(MAC)


async def test_client_connection_error(hass: HomeAssistant, mock_daikin) -> None:
    """Test unique id migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_HOST: HOST, KEY_MAC: MAC},
    )
    config_entry.add_to_hass(hass)

    mock_daikin.factory.side_effect = ClientConnectionError
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_timeout_error(hass: HomeAssistant, mock_daikin) -> None:
    """Test unique id migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_HOST: HOST, KEY_MAC: MAC},
    )
    config_entry.add_to_hass(hass)

    mock_daikin.factory.side_effect = asyncio.TimeoutError
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY
