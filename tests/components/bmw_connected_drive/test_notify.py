"""Test BMW numbers."""

from unittest.mock import AsyncMock

from bimmer_connected.models import MyBMWAPIError, MyBMWRemoteServiceError
from bimmer_connected.tests.common import POI_DATA
from bimmer_connected.vehicle.remote_services import RemoteServices
import pytest
import respx

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import check_remote_service_call, setup_mocked_integration


async def test_legacy_notify_service_simple(
    hass: HomeAssistant,
    bmw_fixture: respx.Router,
) -> None:
    """Test successful sending of POIs."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Minimal required data
    await hass.services.async_call(
        "notify",
        "bmw_connected_drive_ix_xdrive50",
        {
            "message": POI_DATA.get("name"),
            "data": {
                "latitude": POI_DATA.get("lat"),
                "longitude": POI_DATA.get("lon"),
            },
        },
        blocking=True,
    )
    check_remote_service_call(bmw_fixture, "send-to-car")

    bmw_fixture.reset()

    # Full data
    await hass.services.async_call(
        "notify",
        "bmw_connected_drive_ix_xdrive50",
        {
            "message": POI_DATA.get("name"),
            "data": {
                "latitude": POI_DATA.get("lat"),
                "longitude": POI_DATA.get("lon"),
                "street": POI_DATA.get("street"),
                "city": POI_DATA.get("city"),
                "postal_code": POI_DATA.get("postal_code"),
                "country": POI_DATA.get("country"),
            },
        },
        blocking=True,
    )
    check_remote_service_call(bmw_fixture, "send-to-car")


@pytest.mark.usefixtures("bmw_fixture")
@pytest.mark.parametrize(
    ("data", "exc_translation"),
    [
        (
            {
                "latitude": POI_DATA.get("lat"),
            },
            "Invalid data for point of interest: required key not provided @ data['longitude']",
        ),
        (
            {
                "latitude": POI_DATA.get("lat"),
                "longitude": "text",
            },
            "Invalid data for point of interest: invalid longitude for dictionary value @ data['longitude']",
        ),
        (
            {
                "latitude": POI_DATA.get("lat"),
                "longitude": 9999,
            },
            "Invalid data for point of interest: invalid longitude for dictionary value @ data['longitude']",
        ),
    ],
)
async def test_service_call_invalid_input(
    hass: HomeAssistant,
    data: dict,
    exc_translation: str,
) -> None:
    """Test invalid inputs."""

    # Setup component
    assert await setup_mocked_integration(hass)

    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            "notify",
            "bmw_connected_drive_ix_xdrive50",
            {
                "message": POI_DATA.get("name"),
                "data": data,
            },
            blocking=True,
        )
    assert str(exc.value) == exc_translation


@pytest.mark.usefixtures("bmw_fixture")
@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (MyBMWRemoteServiceError, HomeAssistantError),
        (MyBMWAPIError, HomeAssistantError),
    ],
)
async def test_service_call_fail(
    hass: HomeAssistant,
    raised: Exception,
    expected: Exception,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test exception handling."""

    # Setup component
    assert await setup_mocked_integration(hass)

    # Setup exception
    monkeypatch.setattr(
        RemoteServices,
        "trigger_remote_service",
        AsyncMock(side_effect=raised),
    )

    # Test
    with pytest.raises(expected):
        await hass.services.async_call(
            "notify",
            "bmw_connected_drive_ix_xdrive50",
            {
                "message": POI_DATA.get("name"),
                "data": {
                    "latitude": POI_DATA.get("lat"),
                    "longitude": POI_DATA.get("lon"),
                },
            },
            blocking=True,
        )
