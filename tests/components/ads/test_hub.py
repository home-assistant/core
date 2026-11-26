"""Test the ADS hub's connection helpers."""

import asyncio
import threading
from unittest.mock import MagicMock

import pyads
import pytest

from homeassistant.components.ads.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_PORT, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import ADS_CONFIG, MockAdsDevice, setup_ads_platform
from .const import PORT


async def test_platform_waits_for_the_import(
    hass: HomeAssistant,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a YAML platform waits for the imported entry instead of retrying."""
    mock_ads_device.values["GVL.pump"] = b"\x01"

    assert await setup_ads_platform(
        hass,
        mock_ads_device,
        SWITCH_DOMAIN,
        {"adsvar": "GVL.pump", "name": "Pump"},
    )

    assert hass.states.get("switch.pump").state == STATE_ON
    assert "not ready yet" not in caplog.text


async def test_platform_gives_up_without_an_entry(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a YAML platform retries on its own when no entry ever sets up.

    A malformed NetID aborts the import, so the platform does not wait for it.
    """
    async with asyncio.timeout(5):
        assert await async_setup_component(
            hass,
            SWITCH_DOMAIN,
            {
                DOMAIN: {CONF_DEVICE: "bad", CONF_PORT: PORT},
                SWITCH_DOMAIN: {
                    "platform": DOMAIN,
                    "adsvar": "GVL.pump",
                    "name": "Pump",
                },
            },
        )
        await hass.async_block_till_done()

    assert hass.states.get("switch.pump") is None
    assert "The ADS connection is not set up" in caplog.text


async def test_platform_waits_for_a_retry_in_progress(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_ads_device: MockAdsDevice,
) -> None:
    """Test a YAML platform set up during a retry waits for it, not the failure."""
    client = mock_pyads_connection.return_value
    client.read_state.side_effect = pyads.ADSError(err_code=1861)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: ADS_CONFIG})
    await hass.async_block_till_done()
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.state is ConfigEntryState.SETUP_RETRY

    connecting, release = threading.Event(), threading.Event()

    def _slow_read_state() -> tuple[int, int]:
        connecting.set()
        release.wait(5)
        return (pyads.ADSSTATE_RUN, 0)

    client.read_state.side_effect = _slow_read_state
    mock_ads_device.values["GVL.pump"] = b"\x01"
    retry = hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
    await hass.async_add_executor_job(connecting.wait, 5)
    platform = hass.async_create_task(
        async_setup_component(
            hass,
            SWITCH_DOMAIN,
            {SWITCH_DOMAIN: {"platform": DOMAIN, "adsvar": "GVL.pump", "name": "Pump"}},
        )
    )
    for _ in range(20):
        await asyncio.sleep(0)
    release.set()
    await retry
    assert await platform
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("switch.pump").state == STATE_ON
