"""Tests for the seventeentrack service."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.components.seventeentrack import DOMAIN, SERVICE_GET_PACKAGES
from homeassistant.core import HomeAssistant, SupportsResponse

from tests.common import MockConfigEntry
from tests.components.seventeentrack import init_integration
from tests.components.seventeentrack.conftest import get_package


async def test_get_packages_from_list(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Ensure service returns only the packages in the list."""
    await _mock_packages(mock_seventeentrack)
    await init_integration(hass, mock_config_entry)
    service_response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PACKAGES,
        {
            "config_entry_id": mock_config_entry.entry_id,
            "package_state": ["in_transit", "delivered"],
        },
        blocking=True,
        return_response=SupportsResponse.ONLY,
    )

    assert service_response == snapshot


async def test_get_all_packages(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Ensure service returns all packages when non provided."""
    await _mock_packages(mock_seventeentrack)
    await init_integration(hass, mock_config_entry)
    service_response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PACKAGES,
        {
            "config_entry_id": mock_config_entry.entry_id,
        },
        blocking=True,
        return_response=SupportsResponse.ONLY,
    )

    assert service_response == snapshot


async def _mock_packages(mock_seventeentrack):
    package1 = get_package(status=10)
    package2 = get_package(
        tracking_number="789",
        friendly_name="friendly name 2",
        status=40,
    )
    package3 = get_package(
        tracking_number="123",
        friendly_name="friendly name 3",
        status=20,
    )
    mock_seventeentrack.return_value.profile.packages.return_value = [
        package1,
        package2,
        package3,
    ]
