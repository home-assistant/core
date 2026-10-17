"""Tests for the seventeentrack service."""

from unittest.mock import AsyncMock

from pyseventeentrack.errors import RequestError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.seventeentrack import DOMAIN
from homeassistant.components.seventeentrack.const import (
    SERVICE_ARCHIVE_PACKAGE,
    SERVICE_GET_PACKAGES,
    SERVICE_SET_CARRIER,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from . import init_integration
from .conftest import (
    ARCHIVE_PACKAGE_NUMBER,
    CONFIG_ENTRY_ID_KEY,
    PACKAGE_STATE_KEY,
    PACKAGE_TRACKING_NUMBER_KEY,
    get_package,
)

from tests.common import MockConfigEntry


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
            CONFIG_ENTRY_ID_KEY: mock_config_entry.entry_id,
            PACKAGE_STATE_KEY: ["in_transit", "delivered"],
        },
        blocking=True,
        return_response=True,
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
            CONFIG_ENTRY_ID_KEY: mock_config_entry.entry_id,
        },
        blocking=True,
        return_response=True,
    )

    assert service_response == snapshot


async def test_service_called_with_unloaded_entry(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test service call with not ready config entry."""
    await init_integration(hass, mock_config_entry)
    mock_config_entry.mock_state(hass, ConfigEntryState.SETUP_ERROR)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PACKAGES,
            {
                CONFIG_ENTRY_ID_KEY: mock_config_entry.entry_id,
            },
            blocking=True,
            return_response=True,
        )


async def test_service_called_with_non_17track_device(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test service calls with non 17Track device."""
    await init_integration(hass, mock_config_entry)

    other_domain = "Not17Track"
    other_config_id = "555"
    other_mock_config_entry = MockConfigEntry(
        title="Not 17Track", domain=other_domain, entry_id=other_config_id
    )
    other_mock_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=other_config_id,
        identifiers={(other_domain, "1")},
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PACKAGES,
            {
                CONFIG_ENTRY_ID_KEY: device_entry.id,
            },
            blocking=True,
            return_response=True,
        )


async def test_archive_package(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Ensure service archives package."""
    await _mock_packages(mock_seventeentrack)
    await init_integration(hass, mock_config_entry)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ARCHIVE_PACKAGE,
        {
            CONFIG_ENTRY_ID_KEY: mock_config_entry.entry_id,
            PACKAGE_TRACKING_NUMBER_KEY: ARCHIVE_PACKAGE_NUMBER,
        },
        blocking=True,
    )
    mock_seventeentrack.return_value.profile.archive_package.assert_called_once_with(
        ARCHIVE_PACKAGE_NUMBER
    )


@pytest.mark.parametrize(
    ("service_data", "expected_second_carrier"),
    [
        pytest.param({"second_carrier": 19251}, 19251, id="with_second_carrier"),
        pytest.param({}, None, id="keep_second_carrier"),
    ],
)
async def test_set_carrier(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service_data: dict[str, int],
    expected_second_carrier: int | None,
) -> None:
    """Ensure service sets the package carrier and refreshes the coordinator."""
    await init_integration(hass, mock_config_entry)
    mock_seventeentrack.return_value.profile.summary.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_CARRIER,
        {
            CONFIG_ENTRY_ID_KEY: mock_config_entry.entry_id,
            PACKAGE_TRACKING_NUMBER_KEY: ARCHIVE_PACKAGE_NUMBER,
            "first_carrier": 190271,
            **service_data,
        },
        blocking=True,
    )
    mock_seventeentrack.return_value.profile.set_carrier_by_tracking_number.assert_called_once_with(
        ARCHIVE_PACKAGE_NUMBER, 190271, expected_second_carrier
    )
    mock_seventeentrack.return_value.profile.summary.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(RequestError("Non-zero status code"), id="request_error"),
        pytest.param(ValueError("invalid carriers"), id="value_error"),
    ],
)
async def test_set_carrier_error(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Ensure library errors are raised as HomeAssistantError."""
    await init_integration(hass, mock_config_entry)
    mock_seventeentrack.return_value.profile.set_carrier_by_tracking_number.side_effect = error
    with pytest.raises(HomeAssistantError, match="Failed to set the carrier"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_CARRIER,
            {
                CONFIG_ENTRY_ID_KEY: mock_config_entry.entry_id,
                PACKAGE_TRACKING_NUMBER_KEY: ARCHIVE_PACKAGE_NUMBER,
                "first_carrier": 190271,
            },
            blocking=True,
        )


async def test_packages_with_none_timestamp(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Ensure service returns all packages when non provided."""
    await _mock_invalid_packages(mock_seventeentrack)
    await init_integration(hass, mock_config_entry)
    service_response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PACKAGES,
        {
            CONFIG_ENTRY_ID_KEY: mock_config_entry.entry_id,
        },
        blocking=True,
        return_response=True,
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


async def _mock_invalid_packages(mock_seventeentrack):
    package1 = get_package(
        status=10,
        timestamp=None,
    )
    package2 = get_package(
        tracking_number="789",
        friendly_name="friendly name 2",
        status=40,
    )
    mock_seventeentrack.return_value.profile.packages.return_value = [
        package1,
        package2,
    ]
