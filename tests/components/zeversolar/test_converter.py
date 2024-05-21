"""Test the ZeversolarCoordinator class."""

from unittest.mock import patch

from zeversolar import StatusEnum, ZeverSolarClient, ZeverSolarData

from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.components.zeversolar.coordinator import ZeversolarCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from tests.common import MockConfigEntry


async def test_ZeversolarCoordinator_constructor(hass: HomeAssistant) -> None:
    """Simple test for construction and initialization."""

    config = MockConfigEntry(
        data={
            "host": "my host",
            "port": 10200,
        },
        domain=DOMAIN,
        options={},
        title="My NEW_DOMAIN",
    )

    zeversolarCoordinator = ZeversolarCoordinator(hass=hass, entry=config)

    assert type(zeversolarCoordinator) is ZeversolarCoordinator
    assert issubclass(type(zeversolarCoordinator), DataUpdateCoordinator)


async def test_ZeversolarCoordinator_async_update_data(hass) -> None:
    """Tests the async_update_data method."""

    config = MockConfigEntry(
        data={
            "host": "my host",
            "port": 10200,
        },
        domain=DOMAIN,
        options={},
        title="My NEW_DOMAIN",
    )

    data = ZeverSolarData(
        wifi_enabled=False,
        serial_or_registry_id="1223",
        registry_key="A-2",
        hardware_version="M10",
        software_version="123-23",
        reported_datetime="19900101 23:00",
        communication_status=StatusEnum.OK,
        num_inverters=1,
        serial_number="123456778",
        pac=1234,
        energy_today=123,
        status=StatusEnum.OK,
        meter_status=StatusEnum.OK,
    )

    with patch.object(ZeverSolarClient, "get_data") as client_mock:
        coordinator = ZeversolarCoordinator(hass=hass, entry=config)
        client_mock.return_value = data

        await coordinator._async_update_data()
        assert coordinator.last_update_success
