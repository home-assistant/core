"""BleBox devices setup tests."""

from asynctest import call, mock, patch
import blebox_uniapi
import pytest

from homeassistant.components.blebox import async_setup_entry
from homeassistant.components.blebox.const import DOMAIN
from homeassistant.exceptions import ConfigEntryNotReady

from .conftest import mock_config, patch_product_identify


async def test_setup_failure(hass):
    """Test that setup failure is handled and logged."""

    patch_product_identify(None, side_effect=blebox_uniapi.error.ClientError)

    with patch("homeassistant.components.blebox._LOGGER.error") as error:
        with pytest.raises(ConfigEntryNotReady):
            config = mock_config()
            config.add_to_hass(hass)
            await async_setup_entry(hass, config)

        error.assert_has_calls(
            [call("Identify failed at %s:%d (%s)", "172.100.123.4", 80, mock.ANY,)]
        )
        assert isinstance(error.call_args[0][3], blebox_uniapi.error.ClientError)


async def test_setup_failure_on_connection(hass):
    """Test that setup failure is handled and logged."""

    patch_product_identify(None, side_effect=blebox_uniapi.error.ConnectionError)

    with patch("homeassistant.components.blebox._LOGGER.error") as error:
        with pytest.raises(ConfigEntryNotReady):
            config = mock_config()
            config.add_to_hass(hass)
            await async_setup_entry(hass, config)

        error.assert_has_calls(
            [call("Identify failed at %s:%d (%s)", "172.100.123.4", 80, mock.ANY,)]
        )
        assert isinstance(error.call_args[0][3], blebox_uniapi.error.ConnectionError)


async def test_unload_config_entry(hass):
    """Test that unloading works properly."""
    patch_product_identify(None)

    entry = mock_config()

    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.data[DOMAIN]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)
