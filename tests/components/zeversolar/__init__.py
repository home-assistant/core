"""Tests for the Zeversolar integration."""

from unittest.mock import patch

from zeversolar import StatusEnum, ZeverSolarData

from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_HOST_ZEVERSOLAR = "zeversolar-fake-host"
MOCK_PORT_ZEVERSOLAR = 10200
MOCK_SERIAL_NUMBER = "123456778"


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Mock integration setup."""

    zeverData = ZeverSolarData(
        wifi_enabled=False,
        serial_or_registry_id="EAB9615C0001",
        registry_key="WSMQKHTQ3JVYQWA9",
        hardware_version="M10",
        software_version="19703-826R+17511-707R",
        reported_datetime="19900101 23:01:45",
        communication_status=StatusEnum.OK,
        num_inverters=1,
        serial_number=MOCK_SERIAL_NUMBER,
        pac=1234,
        energy_today=123.4,
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
