"""Tests for the NeoPool coordinator."""

from unittest.mock import AsyncMock, MagicMock

from neopool_modbus.decoders import encode_device_time
import pytest

from homeassistant.components.neopool.const import (
    CONF_AUTO_TIME_SYNC,
    CONF_MODBUS_FRAMER,
    CONF_UNIT_ID,
    CURRENT_VERSION,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import MOCK_HOST, MOCK_POOL_DATA, MOCK_PORT

from tests.common import MockConfigEntry


def _entry(*, auto_time_sync: bool) -> MockConfigEntry:
    """Return a config entry with the auto-time-sync option set."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id="neopool_drift",
        version=CURRENT_VERSION,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_NAME: "Pool",
            CONF_UNIT_ID: 1,
            CONF_MODBUS_FRAMER: "tcp",
        },
        options={CONF_AUTO_TIME_SYNC: auto_time_sync},
    )


async def test_auto_time_sync_writes_when_drift_detected(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
) -> None:
    """auto_time_sync delegates to the lib's async_sync_device_time on drift."""
    drifted = dict(MOCK_POOL_DATA)
    drifted["MBF_PAR_TIME"] = int(dt_util.utcnow().timestamp()) - 7200  # 2 hours ago
    mock_neopool_client.async_read_all = AsyncMock(return_value=drifted)

    await setup_integration(hass, _entry(auto_time_sync=True))

    assert mock_neopool_client.async_sync_device_time.await_count == 1


async def test_auto_time_sync_skipped_when_disabled(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
) -> None:
    """A drifted clock is left alone while the option is off."""
    drifted = dict(MOCK_POOL_DATA)
    drifted["MBF_PAR_TIME"] = int(dt_util.utcnow().timestamp()) - 7200
    mock_neopool_client.async_read_all = AsyncMock(return_value=drifted)

    await setup_integration(hass, _entry(auto_time_sync=False))

    mock_neopool_client.async_sync_device_time.assert_not_called()


@pytest.mark.usefixtures("mock_neopool_client")
async def test_auto_time_sync_skipped_when_in_sync(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
) -> None:
    """An in-sync clock does not trigger a write even with the option on."""
    tz = dt_util.get_time_zone(hass.config.time_zone)
    in_sync = dict(MOCK_POOL_DATA)
    # MBF_PAR_TIME is local wall-clock epoch; encode HA's own now so the
    # decoded device time matches and no drift is detected.
    in_sync["MBF_PAR_TIME"] = encode_device_time(dt_util.now(tz))
    mock_neopool_client.async_read_all = AsyncMock(return_value=in_sync)

    await setup_integration(hass, _entry(auto_time_sync=True))

    mock_neopool_client.async_sync_device_time.assert_not_called()
