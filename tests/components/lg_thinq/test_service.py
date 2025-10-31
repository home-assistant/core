"""Tests for the LG Thinq service."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.lg_thinq.const import DOMAIN
from homeassistant.components.lg_thinq.services import ENERGY_SERVICE_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry, async_load_json_object_fixture


async def test_has_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the existence of the service."""
    await setup_integration(hass, mock_config_entry)
    assert hass.services.has_service(DOMAIN, ENERGY_SERVICE_NAME)


@pytest.mark.parametrize(
    ("start_date", "end_date", "reponse_total"),
    [
        (date(2024, 10, 1), date(2024, 10, 10), 550),
        (date(2024, 10, 1), date(2024, 10, 31), 4960),
    ],
)
@pytest.mark.parametrize("device_fixture", ["air_conditioner"])
async def test_energy_service(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_thinq_api: AsyncMock,
    device_fixture: str,
    start_date: date,
    end_date: date,
    reponse_total: int,
) -> None:
    """Test service energy usage."""
    with patch(
        "homeassistant.components.lg_thinq.ThinQMQTT.async_connect",
        return_value=True,
    ):
        await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "MW2-2E247F93-B570-46A6-B827-920E9E10F966")}
    )
    assert device_entry
    data = {
        "device_id": device_entry.id,
        "period": "daily",
        "start_date": start_date,
        "end_date": end_date,
    }
    load_data = f"{device_fixture}/energy_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.json"
    mock_thinq_api.async_get_device_energy_usage.return_value = (
        await async_load_json_object_fixture(hass, load_data, DOMAIN)
    )
    service_response = await hass.services.async_call(
        DOMAIN,
        ENERGY_SERVICE_NAME,
        data,
        blocking=True,
        return_response=True,
    )
    assert service_response["total"] == reponse_total
