"""Tests for BluettiDeviceCoordinator."""

from unittest.mock import AsyncMock

from pybluetti import ApplicationRuntimeException
import pytest

from homeassistant.components.bluetti_cloud.const import DOMAIN
from homeassistant.components.bluetti_cloud.coordinator import BluettiDeviceCoordinator
from homeassistant.components.bluetti_cloud.models import BluettiDevice
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


def _make_device() -> BluettiDevice:
    return BluettiDevice(
        device_id="SN1", on_line="1", name="Test", sn="SN1", model="AC200L"
    )


async def test_coordinator_links_itself_to_the_device(hass: HomeAssistant) -> None:
    """Coordinator links itself to the device."""
    device = _make_device()
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)

    assert device.coordinator is coordinator
    assert coordinator.device is device


async def test_coordinator_update_success(hass: HomeAssistant) -> None:
    """Coordinator update success."""
    device = _make_device()
    device.async_refresh_from_api = AsyncMock()
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    data = await coordinator._async_update_data()

    assert data is device
    device.async_refresh_from_api.assert_awaited_once()


async def test_coordinator_raises_update_failed_on_generic_error(
    hass: HomeAssistant,
) -> None:
    """Coordinator raises update failed on generic error."""
    device = _make_device()
    device.async_refresh_from_api = AsyncMock(side_effect=RuntimeError("boom"))
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_raises_update_failed_on_non_auth_api_error(
    hass: HomeAssistant,
) -> None:
    """Coordinator raises update failed on non auth api error."""
    device = _make_device()
    device.async_refresh_from_api = AsyncMock(
        side_effect=ApplicationRuntimeException(msgCode=500, errMessage="server error")
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.parametrize("msg_code", [401, 805])
async def test_coordinator_raises_auth_failed_on_auth_error_codes(
    hass: HomeAssistant, msg_code: int
) -> None:
    """Coordinator raises auth failed on auth error codes."""
    device = _make_device()
    device.async_refresh_from_api = AsyncMock(
        side_effect=ApplicationRuntimeException(
            msgCode=msg_code, errMessage="unauthorized"
        )
    )
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    coordinator = BluettiDeviceCoordinator(hass, entry, device)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
