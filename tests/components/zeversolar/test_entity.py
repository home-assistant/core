"""Test the ZeversolarEntity."""

from zeversolar import StatusEnum, ZeverSolarData

from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.components.zeversolar.coordinator import ZeversolarCoordinator
from homeassistant.components.zeversolar.entity import ZeversolarEntity
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_ZeversolarEntity_constructor(hass: HomeAssistant) -> None:
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
    zeversolarCoordinator.data = ZeverSolarData(
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

    result_sensor = ZeversolarEntity(coordinator=zeversolarCoordinator)

    assert type(result_sensor) is ZeversolarEntity
