"""Tests for the WLED update platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from wled import Releases, WLEDError

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.components.wled.const import RELEASES_SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.wled.PLATFORMS", [Platform.UPDATE]):
        yield


async def test_update_available(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the update."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    assert (state := hass.states.get("update.wled_rgb_light_firmware"))
    assert state.state == STATE_ON

    assert snapshot == state


async def test_update_information_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    mock_wled_releases: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test having no update information available at all."""
    mock_wled_releases.releases.return_value = Releases(
        beta=None,
        stable=None,
    )

    freezer.tick(RELEASES_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("update.wled_rgb_light_firmware"))
    assert state.state == STATE_UNKNOWN

    assert snapshot == state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_no_update_available(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test there is no update available."""
    assert (state := hass.states.get("update.wled_websocket_firmware"))
    assert state.state == STATE_OFF

    assert snapshot == state


async def test_update_error(
    hass: HomeAssistant,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED update."""
    mock_wled.update.side_effect = WLEDError

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.wled_rgb_light_firmware"},
        blocking=True,
    )

    assert (state := hass.states.get("update.wled_rgb_light_firmware"))
    assert state.state == STATE_UNAVAILABLE
    assert "Invalid response from WLED API" in caplog.text


async def test_update_stay_stable(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test the update entity staying on stable.

    There is both an update for beta and stable available, however, the device
    is currently running a stable version. Therefore, the update entity should
    update to the next stable (even though beta is newer).
    """
    assert (state := hass.states.get("update.wled_rgb_light_firmware"))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.14.4"
    assert state.attributes[ATTR_LATEST_VERSION] == "0.99.0"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.wled_rgb_light_firmware"},
        blocking=True,
    )
    assert mock_wled.upgrade.call_count == 1
    mock_wled.upgrade.assert_called_with(version="0.99.0")


@pytest.mark.parametrize("device_fixture", ["rgbw"])
async def test_update_beta_to_stable(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test the update entity.

    There is both an update for beta and stable available and the device
    is currently a beta, however, a newer stable is available. Therefore, the
    update entity should update to the next stable.
    """
    assert (state := hass.states.get("update.wled_rgbw_light_firmware"))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.99.0b1"
    assert state.attributes[ATTR_LATEST_VERSION] == "0.99.0"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.wled_rgbw_light_firmware"},
        blocking=True,
    )
    assert mock_wled.upgrade.call_count == 1
    mock_wled.upgrade.assert_called_with(version="0.99.0")


@pytest.mark.parametrize("device_fixture", ["rgb_single_segment"])
async def test_update_stay_beta(
    hass: HomeAssistant,
    mock_wled: MagicMock,
) -> None:
    """Test the update entity.

    There is an update for beta and the device is currently a beta. Therefore,
    the update entity should update to the next beta.
    """
    assert (state := hass.states.get("update.wled_rgb_light_firmware"))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0b4"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.0b5"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.wled_rgb_light_firmware"},
        blocking=True,
    )
    assert mock_wled.upgrade.call_count == 1
    mock_wled.upgrade.assert_called_with(version="1.0.0b5")
