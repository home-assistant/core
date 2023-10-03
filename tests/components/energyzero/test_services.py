"""Tests for the sensors provided by the EnergyZero integration."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.energyzero.const import DOMAIN, SERVICE_NAME
from homeassistant.core import HomeAssistant

pytestmark = [pytest.mark.freeze_time("2022-12-07 15:00:00")]


@pytest.mark.usefixtures("init_integration")
async def test_has_service(
    hass: HomeAssistant,
) -> None:
    """Test the existence of the EnergyZero Service."""
    assert hass.services.has_service(DOMAIN, SERVICE_NAME)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("price_type", [{"type": "gas"}, {"type": "energy"}])
@pytest.mark.parametrize("incl_vat", [{"incl_vat": False}, {"incl_vat": True}, {}])
@pytest.mark.parametrize(
    "start", [{"start": "2023-01-01 00:00:00"}, {"start": "incorrect date"}, {}]
)
@pytest.mark.parametrize(
    "end", [{"end": "2023-01-01 00:00:00"}, {"end": "incorrect date"}, {}]
)
async def test_service(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    price_type: dict[str, str],
    incl_vat: dict[str, bool],
    start: dict[str, str],
    end: dict[str, str],
) -> None:
    """Test the EnergyZero Service."""

    data = price_type | incl_vat | start | end

    try:
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_NAME,
            data,
            blocking=True,
            return_response=True,
        )
        assert response == snapshot
    except ValueError as e:
        assert e == snapshot
