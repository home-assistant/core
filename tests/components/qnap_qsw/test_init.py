"""Define tests for the QNAP QSW init."""

from unittest.mock import patch

from aioqsw.exceptions import APIError

from homeassistant.components.qnap_qsw.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .util import CONFIG

from tests.common import MockConfigEntry


async def test_firmware_check_error(hass: HomeAssistant) -> None:
    """Test firmware update check error."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="qsw_unique_id", data=CONFIG
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.check_firmware",
        side_effect=APIError,
    ), patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.validate",
        return_value=None,
    ), patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.update",
        return_value=None,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="qsw_unique_id", data=CONFIG
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.check_firmware",
        return_value=None,
    ), patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.validate",
        return_value=None,
    ), patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.update",
        return_value=None,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED
