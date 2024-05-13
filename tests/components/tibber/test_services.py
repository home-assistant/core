"""Tests for the services provided by the Tibber integration."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tibber.const import DOMAIN
from homeassistant.components.tibber.services import PRICE_SERVICE_NAME
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("init_integration")
async def test_has_services(
    hass: HomeAssistant,
) -> None:
    """Test the existence of the Tibber Service."""
    assert hass.services.has_service(DOMAIN, PRICE_SERVICE_NAME)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "service",
    [
        PRICE_SERVICE_NAME,
    ],
)
@pytest.mark.parametrize("start", [{"start": "2024-05-13 00:00:00"}, {}])
@pytest.mark.parametrize("end", [{"end": "2024-05-14 00:00:00"}, {}])
async def test_service(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    service: str,
    start: dict[str, str],
    end: dict[str, str],
) -> None:
    """Test the Tibber Service."""

    data = start | end

    assert snapshot == await hass.services.async_call(
        DOMAIN,
        service,
        data,
        blocking=True,
        return_response=True,
    )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "service",
    [PRICE_SERVICE_NAME],
)
async def test_service_validation(
    hass: HomeAssistant,
    service: str,
    config_entry_data: dict[str, str],
    service_data: dict[str, str | bool],
    error: type[Exception],
    error_message: str,
) -> None:
    """Test the Tibber Service."""

    with pytest.raises(error, match=error_message):
        await hass.services.async_call(
            DOMAIN,
            service,
            config_entry_data | service_data,
            blocking=True,
            return_response=True,
        )
