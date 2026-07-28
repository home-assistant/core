"""Coverage-gap tests for tick_failure.py's outer exception-handler side effects."""

import aiohttp

from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.components.bosch_shc_camera.coordinator import BoschCameraCoordinator
from homeassistant.components.bosch_shc_camera.tick_failure import (
    dispatch_client_error,
    dispatch_timeout,
    dispatch_update_failed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


def _make_coordinator(hass: HomeAssistant) -> BoschCameraCoordinator:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data={"bearer_token": "tok", "refresh_token": "rtok"},
        options={},
    )
    entry.add_to_hass(hass)
    return BoschCameraCoordinator(hass, entry)


async def test_dispatch_update_failed_spawns_cloud_alert_task(
    hass: HomeAssistant,
) -> None:
    """The cloud-alert coroutine is spawned as a tracked background task."""
    coordinator = _make_coordinator(hass)

    await dispatch_update_failed(coordinator)
    await hass.async_block_till_done()

    assert coordinator._cloud_outage_started_at is not None


async def test_dispatch_timeout_spawns_outage_ping_and_cloud_alert_and_returns_update_failed(
    hass: HomeAssistant,
) -> None:
    """A timeout spawns both the outage-ping and the cloud-alert task."""
    coordinator = _make_coordinator(hass)

    result = await dispatch_timeout(coordinator)
    await hass.async_block_till_done()

    assert isinstance(result, UpdateFailed)
    assert "Timeout fetching camera data" in str(result)
    assert coordinator._cloud_outage_started_at is not None
    # async_outage_ping_all() only pings known cameras; with no camera data
    # it no-ops but still updates the throttle timestamp on the real path —
    # covered indirectly via the spawn not raising.


async def test_dispatch_client_error_spawns_cloud_alert_and_returns_update_failed(
    hass: HomeAssistant,
) -> None:
    """A client error spawns the cloud-alert task and formats the message."""
    coordinator = _make_coordinator(hass)
    err = aiohttp.ClientError("connection reset")

    result = await dispatch_client_error(coordinator, err)
    await hass.async_block_till_done()

    assert isinstance(result, UpdateFailed)
    assert str(result) == "Network error: connection reset"
    assert coordinator._cloud_outage_started_at is not None


async def test_dispatch_update_failed_noop_when_announce_method_missing() -> None:
    """A stub coordinator with no announce method must not raise."""

    class _StubCoordinator:
        pass

    await dispatch_update_failed(_StubCoordinator())  # must not raise


async def test_dispatch_timeout_noop_when_helper_methods_missing() -> None:
    """A stub coordinator missing both helper methods must still return UpdateFailed."""

    class _StubCoordinator:
        pass

    result = await dispatch_timeout(_StubCoordinator())

    assert isinstance(result, UpdateFailed)


async def test_dispatch_client_error_noop_when_announce_method_missing() -> None:
    """A stub coordinator with no announce method must still return UpdateFailed."""

    class _StubCoordinator:
        pass

    err = aiohttp.ClientError("boom")
    result = await dispatch_client_error(_StubCoordinator(), err)

    assert isinstance(result, UpdateFailed)
    assert str(result) == "Network error: boom"
