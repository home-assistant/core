"""Test the Yale Access Bluetooth init."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.yalexs_ble.const import (
    CONF_KEY,
    CONF_LOCAL_NAME,
    CONF_SLOT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import CoreState, HomeAssistant

from . import YALE_ACCESS_LOCK_DISCOVERY_INFO

from tests.common import MockConfigEntry


async def test_setup_retries_when_not_advertising_at_startup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup is retried with a diagnostic reason when not advertising at startup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
            CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
            CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
            CONF_SLOT: 66,
        },
        unique_id=YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
    )
    entry.add_to_hass(hass)

    hass.set_state(CoreState.starting)

    push_lock = MagicMock()
    push_lock.start = AsyncMock(return_value=MagicMock())

    with (
        patch("homeassistant.components.yalexs_ble.close_stale_connections_by_address"),
        patch("homeassistant.components.yalexs_ble.PushLock", return_value=push_lock),
        patch(
            "homeassistant.components.yalexs_ble.bluetooth."
            "async_address_reachability_diagnostics",
            return_value="mock reachability reason",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        f"{YALE_ACCESS_LOCK_DISCOVERY_INFO.name} "
        f"({YALE_ACCESS_LOCK_DISCOVERY_INFO.address}) is not advertising yet: "
        "mock reachability reason" in caplog.text
    )
