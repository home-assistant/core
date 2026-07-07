"""Test the eq3btsmart integration init."""

from unittest.mock import patch

import pytest

from homeassistant.components.eq3btsmart.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from .const import MAC

from tests.common import MockConfigEntry


async def test_setup_retries_when_device_not_found(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup is retried with a diagnostic reason when the device is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MAC: MAC},
        unique_id=format_mac(MAC),
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.eq3btsmart.bluetooth."
        "async_address_reachability_diagnostics",
        return_value="mock reachability reason",
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        f"[{format_mac(MAC)}] Device could not be found: mock reachability reason"
        in caplog.text
    )
