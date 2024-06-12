"""Tests for the Zeversolar integration."""

from unittest.mock import patch

from zeversolar import StatusEnum, ZeverSolarData

from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_HOST_ZEVERSOLAR = "zeversolar-fake-host"
MOCK_PORT_ZEVERSOLAR = 10200


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Mock integration setup."""

    zeverData = ZeverSolarData(
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

    with (
        patch("zeversolar.ZeverSolarClient.get_data", return_value=zeverData),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: MOCK_HOST_ZEVERSOLAR,
                CONF_PORT: MOCK_PORT_ZEVERSOLAR,
            },
            entry_id="my_id",
        )

        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry
