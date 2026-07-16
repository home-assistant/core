"""Test the AirTouch 4 setup."""

from unittest.mock import AsyncMock, Mock, patch

from airtouch4pyapi.airtouch import (
    AirTouch,
    AirTouchAc,
    AirTouchGroup,
    AirTouchStatus,
    AirTouchVersion,
)

from homeassistant.components.airtouch4.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _mock_airtouch(acs, groups, status=AirTouchStatus.OK):
    """Build an AirTouch whose network calls are stubbed out."""
    airtouch = AirTouch("")
    airtouch.UpdateInfo = AsyncMock()
    airtouch.Status = status
    airtouch.GetAcs = Mock(return_value=acs)
    airtouch.GetGroups = Mock(return_value=groups)
    return airtouch


async def test_setup_entry_builds_client_for_v4(hass: HomeAssistant) -> None:
    """A reachable console loads, and the client is pinned to AirTouch 4 / 9004.

    Passing the version and port explicitly stops the library from running its
    findVersion() port-probe, which opens a blocking socket in the event loop.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.2.3.4"})
    entry.add_to_hass(hass)

    ac = AirTouchAc()
    ac.PowerState = True
    group = AirTouchGroup()
    group.GroupNumber = 0
    group.GroupName = "Living"
    group.PowerState = True
    mock_airtouch = _mock_airtouch([ac], [group])

    with (
        patch(
            "homeassistant.components.airtouch4.AirTouch",
            return_value=mock_airtouch,
        ) as mock_ctor,
        # Keep this test scoped to __init__.py; the climate platform is covered
        # elsewhere.
        patch("homeassistant.components.airtouch4.PLATFORMS", []),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_ctor.assert_called_once_with("1.2.3.4", AirTouchVersion.AIRTOUCH4, 9004)


async def test_setup_entry_no_acs_is_retryable(hass: HomeAssistant) -> None:
    """An unreachable console (no ACs) is retryable, not a terminal error."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.2.3.4"})
    entry.add_to_hass(hass)

    mock_airtouch = _mock_airtouch([], [], status=AirTouchStatus.CONNECTION_LOST)
    with patch(
        "homeassistant.components.airtouch4.AirTouch",
        return_value=mock_airtouch,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_dropped_connection_is_retryable(hass: HomeAssistant) -> None:
    """Regression: a dropped console connection must be retryable, not fatal.

    Exercises the real library with only the socket layer mocked. On
    airtouch4pyapi 1.0.5 a failed connect left a local unbound and UpdateInfo()
    raised UnboundLocalError, which is not ConfigEntryNotReady, so HA latched the
    entry to the terminal setup_error state and never retried. This proves setup
    now ends in SETUP_RETRY, and that the blocking findVersion()/isOpen() probe
    never runs because the version is supplied explicitly.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.2.3.4"})
    entry.add_to_hass(hass)

    async def _drop(*args, **kwargs):
        raise OSError("connection reset by peer")

    mock_is_open = AsyncMock(return_value=False)
    with (
        patch(
            "airtouch4pyapi.communicate.SendMessagePacketToAirtouch",
            side_effect=_drop,
        ),
        patch("airtouch4pyapi.airtouch.AirTouch.isOpen", mock_is_open),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_is_open.assert_not_called()
