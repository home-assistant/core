"""Define tests for the Daikin init."""

from datetime import timedelta
from unittest.mock import AsyncMock, PropertyMock, patch

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.daikin import DaikinApi, update_unique_id
from homeassistant.components.daikin.const import DOMAIN, KEY_MAC
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .test_config_flow import HOST, MAC

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def mock_daikin():
    """Mock pydaikin."""

    async def mock_daikin_factory(*args, **kwargs):
        """Mock the init function in pydaikin."""
        return Appliance

    with patch("homeassistant.components.daikin.Appliance") as Appliance:
        Appliance.factory.side_effect = mock_daikin_factory
        type(Appliance).update_status = AsyncMock()
        type(Appliance).device_ip = PropertyMock(return_value=HOST)
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


async def test_duplicate_removal(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_daikin,
) -> None:
    """Test duplicate device removal."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        title=None,
        data={CONF_HOST: HOST, KEY_MAC: HOST},
    )
    config_entry.add_to_hass(hass)

    type(mock_daikin).mac = PropertyMock(return_value=HOST)
    type(mock_daikin).values = PropertyMock(return_value=INVALID_DATA)

    with patch(
        "homeassistant.components.daikin.async_migrate_unique_id", return_value=None
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        assert config_entry.unique_id != MAC

        type(mock_daikin).mac = PropertyMock(return_value=MAC)
        type(mock_daikin).values = PropertyMock(return_value=DATA)

        assert await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert (
            device_registry.async_get_device({}, {(KEY_MAC, MAC)}).name
            == "DaikinAP00000"
        )

        assert device_registry.async_get_device({}, {(KEY_MAC, HOST)}).name is None

        assert entity_registry.async_get("climate.daikin_127_0_0_1").unique_id == HOST
        assert entity_registry.async_get("switch.none_zone_1").unique_id.startswith(
            HOST
        )

        assert entity_registry.async_get("climate.daikinap00000").unique_id == MAC
        assert entity_registry.async_get(
            "switch.daikinap00000_zone_1"
        ).unique_id.startswith(MAC)

    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device({}, {(KEY_MAC, MAC)}).name == "DaikinAP00000"
    )

    assert entity_registry.async_get("climate.daikinap00000") is None
    assert entity_registry.async_get("switch.daikinap00000_zone_1") is None

    assert entity_registry.async_get("climate.daikin_127_0_0_1").unique_id == MAC
    assert entity_registry.async_get("switch.none_zone_1").unique_id.startswith(MAC)


async def test_unique_id_migrate(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_daikin,
) -> None:
    """Test unique id migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        title=None,
        data={CONF_HOST: HOST, KEY_MAC: HOST},
    )
    config_entry.add_to_hass(hass)

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


async def test_client_update_connection_error(
    hass: HomeAssistant, mock_daikin, freezer: FrozenDateTimeFactory
) -> None:
    """Test client connection error on update."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_HOST: HOST, KEY_MAC: MAC},
    )
    config_entry.add_to_hass(hass)

    type(mock_daikin).mac = PropertyMock(return_value=MAC)
    type(mock_daikin).values = PropertyMock(return_value=DATA)

    await hass.config_entries.async_setup(config_entry.entry_id)

    api: DaikinApi = hass.data[DOMAIN][config_entry.entry_id]

    assert api.available is True

    type(mock_daikin).update_status.side_effect = ClientConnectionError

    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)

    await hass.async_block_till_done()

    assert api.available is False

    assert mock_daikin.update_status.call_count == 2


async def test_client_connection_error(hass: HomeAssistant, mock_daikin) -> None:
    """Test client connection error on setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_HOST: HOST, KEY_MAC: MAC},
    )
    config_entry.add_to_hass(hass)

    mock_daikin.factory.side_effect = ClientConnectionError
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_timeout_error(hass: HomeAssistant, mock_daikin) -> None:
    """Test timeout error on setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_HOST: HOST, KEY_MAC: MAC},
    )
    config_entry.add_to_hass(hass)

    mock_daikin.factory.side_effect = TimeoutError
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
