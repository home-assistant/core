"""Test the init file for the Insteon component."""
import asyncio
from unittest.mock import patch

from pyinsteon.address import Address

from homeassistant.components import insteon
from homeassistant.components.insteon.const import (
    CONF_CAT,
    CONF_OVERRIDE,
    CONF_SUBCAT,
    CONF_X10,
    DOMAIN,
    PORT_HUB_V1,
    PORT_HUB_V2,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import (
    MOCK_ADDRESS,
    MOCK_CAT,
    MOCK_IMPORT_CONFIG_PLM,
    MOCK_IMPORT_FULL_CONFIG_HUB_V1,
    MOCK_IMPORT_FULL_CONFIG_HUB_V2,
    MOCK_IMPORT_FULL_CONFIG_PLM,
    MOCK_IMPORT_MINIMUM_HUB_V1,
    MOCK_IMPORT_MINIMUM_HUB_V2,
    MOCK_SUBCAT,
    MOCK_USER_INPUT_PLM,
    PATCH_CONNECTION,
)
from .mock_devices import MockDevices

from tests.common import MockConfigEntry


async def mock_successful_connection(*args, **kwargs):
    """Return a successful connection."""
    return True


async def mock_failed_connection(*args, **kwargs):
    """Return a failed connection."""
    raise ConnectionError("Connection failed")


async def test_setup_entry(hass: HomeAssistant):
    """Test setting up the entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)

    with patch.object(
        insteon, "async_connect", new=mock_successful_connection
    ), patch.object(insteon, "async_close") as mock_close, patch.object(
        insteon, "devices", new=MockDevices()
    ):
        assert await async_setup_component(
            hass,
            insteon.DOMAIN,
            {},
        )
        await hass.async_block_till_done()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        # pylint: disable=no-member
        assert insteon.devices.async_save.call_count == 1
        assert mock_close.called


async def test_import_plm(hass: HomeAssistant):
    """Test setting up the entry from YAML to a PLM."""
    config = {}
    config[DOMAIN] = MOCK_IMPORT_CONFIG_PLM

    with patch.object(
        insteon, "async_connect", new=mock_successful_connection
    ), patch.object(insteon, "close_insteon_connection"), patch.object(
        insteon, "devices", new=MockDevices()
    ), patch(
        PATCH_CONNECTION, new=mock_successful_connection
    ):
        assert await async_setup_component(
            hass,
            insteon.DOMAIN,
            config,
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.01)
    assert hass.config_entries.async_entries(DOMAIN)
    data = hass.config_entries.async_entries(DOMAIN)[0].data
    assert data[CONF_DEVICE] == MOCK_IMPORT_CONFIG_PLM[CONF_PORT]
    assert CONF_PORT not in data


async def test_import_hub1(hass: HomeAssistant):
    """Test setting up the entry from YAML to a hub v1."""
    config = {}
    config[DOMAIN] = MOCK_IMPORT_MINIMUM_HUB_V1

    with patch.object(
        insteon, "async_connect", new=mock_successful_connection
    ), patch.object(insteon, "close_insteon_connection"), patch.object(
        insteon, "devices", new=MockDevices()
    ), patch(
        PATCH_CONNECTION, new=mock_successful_connection
    ):
        assert await async_setup_component(
            hass,
            insteon.DOMAIN,
            config,
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.01)
        assert hass.config_entries.async_entries(DOMAIN)
    data = hass.config_entries.async_entries(DOMAIN)[0].data
    assert data[CONF_HOST] == MOCK_IMPORT_FULL_CONFIG_HUB_V1[CONF_HOST]
    assert data[CONF_PORT] == PORT_HUB_V1
    assert CONF_USERNAME not in data
    assert CONF_PASSWORD not in data


async def test_import_hub2(hass: HomeAssistant):
    """Test setting up the entry from YAML to a hub v2."""
    config = {}
    config[DOMAIN] = MOCK_IMPORT_MINIMUM_HUB_V2

    with patch.object(
        insteon, "async_connect", new=mock_successful_connection
    ), patch.object(insteon, "close_insteon_connection"), patch.object(
        insteon, "devices", new=MockDevices()
    ), patch(
        PATCH_CONNECTION, new=mock_successful_connection
    ):
        assert await async_setup_component(
            hass,
            insteon.DOMAIN,
            config,
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.01)
        assert hass.config_entries.async_entries(DOMAIN)
    data = hass.config_entries.async_entries(DOMAIN)[0].data
    assert data[CONF_HOST] == MOCK_IMPORT_FULL_CONFIG_HUB_V2[CONF_HOST]
    assert data[CONF_PORT] == PORT_HUB_V2
    assert data[CONF_USERNAME] == MOCK_IMPORT_MINIMUM_HUB_V2[CONF_USERNAME]
    assert data[CONF_PASSWORD] == MOCK_IMPORT_MINIMUM_HUB_V2[CONF_PASSWORD]


async def test_import_options(hass: HomeAssistant):
    """Test setting up the entry from YAML including options."""
    config = {}
    config[DOMAIN] = MOCK_IMPORT_FULL_CONFIG_PLM

    with patch.object(
        insteon, "async_connect", new=mock_successful_connection
    ), patch.object(insteon, "close_insteon_connection"), patch.object(
        insteon, "devices", new=MockDevices()
    ), patch(
        PATCH_CONNECTION, new=mock_successful_connection
    ):
        assert await async_setup_component(
            hass,
            insteon.DOMAIN,
            config,
        )
        await hass.async_block_till_done()
        await asyncio.sleep(0.01)  # Need to yield to async processes
        # pylint: disable=no-member
        assert insteon.devices.add_x10_device.call_count == 2
        assert insteon.devices.set_id.call_count == 1
    options = hass.config_entries.async_entries(DOMAIN)[0].options
    assert len(options[CONF_OVERRIDE]) == 1
    assert options[CONF_OVERRIDE][0][CONF_ADDRESS] == str(Address(MOCK_ADDRESS))
    assert options[CONF_OVERRIDE][0][CONF_CAT] == MOCK_CAT
    assert options[CONF_OVERRIDE][0][CONF_SUBCAT] == MOCK_SUBCAT

    assert len(options[CONF_X10]) == 2
    assert options[CONF_X10][0] == MOCK_IMPORT_FULL_CONFIG_PLM[CONF_X10][0]
    assert options[CONF_X10][1] == MOCK_IMPORT_FULL_CONFIG_PLM[CONF_X10][1]


async def test_import_failed_connection(hass: HomeAssistant):
    """Test a failed connection in import does not create a config entry."""
    config = {}
    config[DOMAIN] = MOCK_IMPORT_CONFIG_PLM

    with patch.object(
        insteon, "async_connect", new=mock_failed_connection
    ), patch.object(insteon, "async_close"), patch.object(
        insteon, "devices", new=MockDevices(connected=False)
    ):
        assert await async_setup_component(
            hass,
            insteon.DOMAIN,
            config,
        )
        await hass.async_block_till_done()
        assert not hass.config_entries.async_entries(DOMAIN)


async def test_setup_entry_failed_connection(hass: HomeAssistant, caplog):
    """Test setting up the entry with a failed connection."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT_PLM)
    config_entry.add_to_hass(hass)

    with patch.object(
        insteon, "async_connect", new=mock_failed_connection
    ), patch.object(insteon, "devices", new=MockDevices(connected=False)):
        assert await async_setup_component(
            hass,
            insteon.DOMAIN,
            {},
        )
        assert "Could not connect to Insteon modem" in caplog.text
