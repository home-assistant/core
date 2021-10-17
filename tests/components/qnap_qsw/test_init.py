"""Define tests for the QNAP QSW init."""

import requests_mock

from homeassistant.components.qnap_qsw.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .util import qnap_qsw_requests_mock

from tests.common import MockConfigEntry

CONFIG = {
    CONF_HOST: "192.168.1.200",
    CONF_PASSWORD: "pass",
    CONF_USERNAME: "admin",
}


async def test_unload_entry(hass):
    """Test unload."""

    with requests_mock.mock() as _m:
        qnap_qsw_requests_mock(_m)

        config_entry = MockConfigEntry(
            domain=DOMAIN, unique_id="qnap_qsw_unique_id", data=CONFIG
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED
