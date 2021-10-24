"""Define tests for the QNAP QSW init."""

import requests_mock

from homeassistant.components.qnap_qsw.const import DOMAIN, SERVICE_REBOOT
from homeassistant.config_entries import ConfigEntryState

from .util import CONFIG, qnap_qsw_requests_mock

from tests.common import MockConfigEntry


async def test_service_reboot(hass):
    """Test reboot service."""

    with requests_mock.mock() as _m:
        qnap_qsw_requests_mock(_m)

        entry = MockConfigEntry(domain=DOMAIN, data=CONFIG)
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.services.has_service(DOMAIN, SERVICE_REBOOT)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_REBOOT,
            blocking=True,
        )
        await hass.async_block_till_done()


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
