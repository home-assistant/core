"""Tests for the LG Thinq service."""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.lg_thinq import services
from homeassistant.components.lg_thinq.const import DOMAIN
from homeassistant.components.lg_thinq.services import ENERGY_SERVICE_NAME
from homeassistant.core import HomeAssistant

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
        (date(2024, 10, 1), date(2024, 10, 5), 150),
        (date(2024, 10, 1), date(2024, 10, 10), 550),
        (date(2024, 10, 10), date(2024, 10, 10), 100),
    ],
)
async def test_energy_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    start_date: date,
    end_date: date,
    reponse_total: int,
) -> None:
    """Test service energy usage."""
    await setup_integration(hass, mock_config_entry)
    data = {
        "device_id": "test_device",
        "period": "daily",
        "start_date": start_date,
        "end_date": end_date,
    }
    mock_coordinator = MagicMock()
    mock_coordinator.device_name = "test_device"
    mock_coordinator.unique_id = "test_unique_id"
    load_list = (
        await async_load_json_object_fixture(hass, "energy_service.json", DOMAIN)
    )["result"]["dataList"]
    target_list = []
    for data_usage in load_list:
        date = datetime.strptime(data_usage["usedDate"], "%Y%m%d").date()
        if start_date <= date <= end_date:
            target_list.append(data_usage)

    mock_coordinator.api.async_get_energy_usage = AsyncMock(return_value=target_list)
    # coordinator mocking
    services.__get_coordinator = MagicMock(return_value=mock_coordinator)
    service_response = await hass.services.async_call(
        DOMAIN,
        ENERGY_SERVICE_NAME,
        data,
        blocking=True,
        return_response=True,
    )
    assert service_response["total"] == reponse_total
