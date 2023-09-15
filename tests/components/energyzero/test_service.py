"""Tests for the sensors provided by the EnergyZero integration."""
from unittest.mock import MagicMock

from energyzero import EnergyZeroNoDataError
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.energyzero.const import DOMAIN, SERVICE_NAME, LOGGER
from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

pytestmark = [pytest.mark.freeze_time("2022-12-07 15:00:00")]


@pytest.mark.parametrize("type", ["gas", "energy", "all"])
@pytest.mark.parametrize("incl_btw", [True, False, None])
@pytest.mark.usefixtures("start", ["2023-01-01 00:00:00", None])
@pytest.mark.usefixtures("end", ["2023-01-01 00:00:00", None])
async def test_service(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    type: str,
    incl_btw: bool,
    start: str,
    end: str,
) -> None:
    """Test the EnergyZero - No gas sensors available."""
    await async_setup_component(hass, DOMAIN, {})

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
    )
    await hass.async_block_till_done()

    LOGGER.debug("response: %s", response)
