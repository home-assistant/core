"""Tests for the seventeentrack service."""

from json import JSONDecodeError
from unittest.mock import AsyncMock

import probatio
from pyseventeentrack.errors import RequestError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.seventeentrack import DOMAIN
from homeassistant.components.seventeentrack.const import (
    ATTR_PACKAGE_FRIENDLY_NAME,
    SERVICE_ADD_PACKAGE,
    SERVICE_ARCHIVE_PACKAGE,
    SERVICE_GET_PACKAGES,
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

TRACKING_NUMBER = "1234567890"
FRIENDLY_NAME = "Test package"


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


@pytest.mark.parametrize(
    ("carrier_data", "first_carrier", "second_carrier"),
    [
        pytest.param({}, None, None, id="auto-detect"),
        pytest.param({"first_carrier": 190271}, 190271, None, id="first-carrier"),
        pytest.param(
            {"first_carrier": 190271, "second_carrier": 100003},
            190271,
            100003,
            id="both-carriers",
        ),
        pytest.param(
            {"first_carrier": "190271", "second_carrier": "100003"},
            190271,
            100003,
            id="carrier-codes-as-text",
        ),
    ],
)
async def test_add_package(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    carrier_data: dict[str, int | str],
    first_carrier: int | None,
    second_carrier: int | None,
) -> None:
    """Pass the requested carrier codes to 17TRACK."""
    await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_PACKAGE,
        {
            CONFIG_ENTRY_ID_KEY: mock_config_entry.entry_id,
            PACKAGE_TRACKING_NUMBER_KEY: TRACKING_NUMBER,
            ATTR_PACKAGE_FRIENDLY_NAME: FRIENDLY_NAME,
            **carrier_data,
        },
        blocking=True,
    )

    mock_seventeentrack.return_value.profile.add_package.assert_awaited_once_with(
        TRACKING_NUMBER,
        FRIENDLY_NAME,
        first_carrier=first_carrier,
        second_carrier=second_carrier,
    )


@pytest.mark.parametrize(
    "carrier_data",
    [
        pytest.param({"second_carrier": 100003}, id="missing-first-carrier"),
        pytest.param({"first_carrier": 0}, id="zero-first-carrier"),
        pytest.param({"first_carrier": True}, id="boolean-first-carrier"),
        pytest.param({"first_carrier": 190271.5}, id="fractional-first-carrier"),
        pytest.param({"first_carrier": ""}, id="empty-first-carrier"),
        pytest.param({"first_carrier": "190271.5"}, id="fractional-carrier-text"),
        pytest.param(
            {"first_carrier": 190271, "second_carrier": 0},
            id="zero-second-carrier",
        ),
    ],
)
async def test_add_package_rejects_invalid_carriers(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    carrier_data: dict[str, int | float | str],
) -> None:
    """Reject invalid carrier data before adding a package."""
    await init_integration(hass, mock_config_entry)

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PACKAGE,
            {
                CONFIG_ENTRY_ID_KEY: mock_config_entry.entry_id,
                PACKAGE_TRACKING_NUMBER_KEY: TRACKING_NUMBER,
                ATTR_PACKAGE_FRIENDLY_NAME: FRIENDLY_NAME,
                **carrier_data,
            },
            blocking=True,
        )

    mock_seventeentrack.return_value.profile.add_package.assert_not_awaited()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(RequestError(), id="api-error"),
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(
            JSONDecodeError("Invalid response", "<html>", 0),
            id="malformed-json",
        ),
    ],
)
async def test_add_package_reports_api_failure(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Report when 17TRACK cannot complete the action."""
    await init_integration(hass, mock_config_entry)
    mock_seventeentrack.return_value.profile.add_package.side_effect = error

    with pytest.raises(
        HomeAssistantError, match="It may already be in your 17TRACK account"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PACKAGE,
            {
                CONFIG_ENTRY_ID_KEY: mock_config_entry.entry_id,
                PACKAGE_TRACKING_NUMBER_KEY: TRACKING_NUMBER,
                ATTR_PACKAGE_FRIENDLY_NAME: FRIENDLY_NAME,
                "first_carrier": 190271,
            },
            blocking=True,
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
