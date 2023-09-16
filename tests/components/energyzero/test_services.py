"""Tests for the sensors provided by the EnergyZero integration."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.energyzero.const import DOMAIN, SERVICE_NAME
from homeassistant.core import HomeAssistant

pytestmark = [pytest.mark.freeze_time("2022-12-07 15:00:00")]


@pytest.mark.parametrize("type", ["gas", "energy", "all"])
@pytest.mark.parametrize("incl_btw", [True, False, None])
@pytest.mark.parametrize("start", ["2023-01-01 00:00:00", None])
@pytest.mark.parametrize("end", ["2023-01-01 00:00:00", None])
@pytest.mark.usefixtures("mock_energyzero")
@pytest.mark.usefixtures("init_integration")
async def test_service(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    type: str,
    incl_btw: bool,
    start: str,
    end: str,
) -> None:
    """Test the EnergyZero - Service."""
    data = {
        "type": type,
    }

    if incl_btw is not None:
        data["incl_btw"] = incl_btw
    if start is not None:
        data["start"] = start
    if end is not None:
        data["end"] = end

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_NAME,
        data,
        blocking=True,
        return_response=True,
    )

    assert response == snapshot
