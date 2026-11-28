"""Tests for the Xiaomi Miio integration setup."""

from collections.abc import Generator
import errno
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from miio import DeviceException
from miio.integrations.airpurifier.zhimi.airpurifier_miot import AirPurifierMiotStatus
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.xiaomi_miio.const import (
    CONF_FLOW_TYPE,
    DOMAIN,
    MODEL_AIRPURIFIER_4_LITE_RMB1,
)
from homeassistant.components.xiaomi_miio.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_TOKEN,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant

from . import TEST_MAC

PURIFIER_ENTITY_ID = "fan.test_purifier"


@pytest.fixture
def mock_air_purifier() -> Generator[MagicMock]:
    """Mock a Xiaomi Air Purifier 4 Lite."""
    mock_purifier = MagicMock()
    mock_purifier.status.return_value = AirPurifierMiotStatus(
        {"power": True, "mode": 0, "fan_level": 1}, MODEL_AIRPURIFIER_4_LITE_RMB1
    )
    with (
        patch(
            "homeassistant.components.xiaomi_miio.get_platforms",
            return_value=[Platform.FAN],
        ),
        patch(
            "homeassistant.components.xiaomi_miio.AirPurifierMiot",
            return_value=mock_purifier,
        ),
    ):
        yield mock_purifier


async def test_setup_unsupported_model(hass: HomeAssistant) -> None:
    """Test setup fails for an unsupported device model."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        title="Unsupported device",
        data={
            CONF_FLOW_TYPE: CONF_DEVICE,
            CONF_HOST: "192.168.1.100",
            CONF_TOKEN: "12345678901234567890123456789012",
            CONF_MODEL: "unsupported.model.v1",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Unsupported Xiaomi Miio device model: unsupported.model.v1"


@pytest.mark.parametrize(
    ("side_effect", "message"),
    [
        pytest.param(
            OSError(errno.ENETUNREACH, "Network is unreachable"),
            "Error fetching test_purifier data: [Errno 101] Network is unreachable",
            id="network_unreachable",
        ),
        pytest.param(
            DeviceException("Unable to discover the device 192.168.1.100"),
            "Error fetching test_purifier data: "
            "Unable to discover the device 192.168.1.100",
            id="device_exception",
        ),
        pytest.param(
            TimeoutError,
            "Timeout fetching test_purifier data",
            id="timeout",
        ),
    ],
)
async def test_update_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_air_purifier: MagicMock,
    side_effect: Exception | type[Exception],
    message: str,
) -> None:
    """Test a failing update makes the device unavailable and is logged once."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        title="test_purifier",
        data={
            CONF_FLOW_TYPE: CONF_DEVICE,
            CONF_HOST: "192.168.1.100",
            CONF_TOKEN: "12345678901234567890123456789012",
            CONF_MODEL: MODEL_AIRPURIFIER_4_LITE_RMB1,
            CONF_MAC: TEST_MAC,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(PURIFIER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    mock_air_purifier.status.side_effect = side_effect
    # Poll twice: only the change to unavailable is logged
    for _ in range(2):
        freezer.tick(UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(PURIFIER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert caplog.text.count(message) == 1
    assert "Unexpected error" not in caplog.text
