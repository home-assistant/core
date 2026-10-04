"""Tests for the LaMetric select platform."""

from datetime import time
from unittest.mock import MagicMock

from demetriek import (
    BrightnessMode,
    LaMetricConnectionError,
    LaMetricError,
    ScreensaverMode,
)
import pytest

from homeassistant.components.lametric.const import DOMAIN
from homeassistant.components.select import (
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_OPTION,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_brightness_mode(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the LaMetric brightness mode controls."""
    state = hass.states.get("select.frenck_s_lametric_brightness_mode")
    assert state
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "Frenck's LaMetric Brightness mode"
    )
    assert state.attributes.get(ATTR_OPTIONS) == ["auto", "manual"]
    assert state.state == BrightnessMode.AUTO

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry.entity_category is EntityCategory.CONFIG
    assert entry.unique_id == "SA110405124500W00BS9-brightness_mode"

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device.configuration_url == "https://127.0.0.1/"
    assert device.connections == {
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff"),
        (dr.CONNECTION_BLUETOOTH, "aa:bb:cc:dd:ee:ee"),
    }
    assert device.entry_type is None
    assert device.hw_version is None
    assert device.identifiers == {(DOMAIN, "SA110405124500W00BS9")}
    assert device.manufacturer == "LaMetric Inc."
    assert device.name == "Frenck's LaMetric"
    assert device.serial_number == "SA110405124500W00BS9"
    assert device.sw_version == "2.2.2"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.frenck_s_lametric_brightness_mode",
            ATTR_OPTION: "manual",
        },
        blocking=True,
    )

    assert len(mock_lametric.display.mock_calls) == 1
    mock_lametric.display.assert_called_once_with(brightness_mode=BrightnessMode.MANUAL)


async def test_select_error(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test error handling of the LaMetric selects."""
    mock_lametric.display.side_effect = LaMetricError

    state = hass.states.get("select.frenck_s_lametric_brightness_mode")
    assert state
    assert state.state == BrightnessMode.AUTO

    with pytest.raises(
        HomeAssistantError, match="Invalid response from the LaMetric device"
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.frenck_s_lametric_brightness_mode",
                ATTR_OPTION: "manual",
            },
            blocking=True,
        )

    state = hass.states.get("select.frenck_s_lametric_brightness_mode")
    assert state
    assert state.state == BrightnessMode.AUTO


async def test_select_connection_error(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test connection error handling of the LaMetric selects."""
    mock_lametric.display.side_effect = LaMetricConnectionError

    state = hass.states.get("select.frenck_s_lametric_brightness_mode")
    assert state
    assert state.state == BrightnessMode.AUTO

    with pytest.raises(
        HomeAssistantError, match="Error communicating with the LaMetric device"
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.frenck_s_lametric_brightness_mode",
                ATTR_OPTION: "manual",
            },
            blocking=True,
        )

    state = hass.states.get("select.frenck_s_lametric_brightness_mode")
    assert state
    assert state.state == STATE_UNAVAILABLE


ENTITY_SCREENSAVER_MODE = "select.frenck_s_lametric_screensaver_mode"


async def test_screensaver_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the screensaver mode select offers the modes the device reports."""
    state = hass.states.get(ENTITY_SCREENSAVER_MODE)
    assert state
    assert state.state == "time_based"
    assert state.attributes.get(ATTR_OPTIONS) == ["time_based", "when_dark"]

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.entity_category is EntityCategory.CONFIG
    assert entry.unique_id == "SA110405124500W00BS9-screensaver_mode"


async def test_screensaver_mode_when_dark(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test switching to the when dark screensaver mode."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_SCREENSAVER_MODE, ATTR_OPTION: "when_dark"},
        blocking=True,
    )

    mock_lametric.display.assert_called_once_with(
        screensaver_mode=ScreensaverMode.WHEN_DARK, screensaver_mode_enabled=True
    )


async def test_screensaver_mode_time_based(
    hass: HomeAssistant,
    mock_lametric: MagicMock,
) -> None:
    """Test switching to the time based mode sends its times along.

    The device only takes the time based mode together with its times.
    """
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_SCREENSAVER_MODE, ATTR_OPTION: "time_based"},
        blocking=True,
    )

    mock_lametric.display.assert_called_once_with(
        screensaver_mode=ScreensaverMode.TIME_BASED,
        screensaver_mode_enabled=True,
        screensaver_start_time=time(0, 0, 39),
        screensaver_end_time=time(6, 30),
    )


async def test_screensaver_mode_time_based_without_times(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lametric: MagicMock,
) -> None:
    """Test the time based mode needs its times set first."""
    time_based = mock_lametric.device.return_value.display.screensaver.modes.time_based
    time_based.enabled = False
    time_based.start_time = None
    time_based.end_time = None
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_SCREENSAVER_MODE)
    assert state
    assert state.state == "unknown"

    with pytest.raises(ServiceValidationError, match="start and end time first"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_SCREENSAVER_MODE, ATTR_OPTION: "time_based"},
            blocking=True,
        )

    mock_lametric.display.assert_not_called()


@pytest.mark.parametrize("device_fixture", ["device_sa5_bluetooth_unavailable"])
async def test_no_screensaver_mode_on_sky(hass: HomeAssistant) -> None:
    """Test the SKY gets no screensaver mode select."""
    assert hass.states.get("select.sky_screensaver_mode") is None
