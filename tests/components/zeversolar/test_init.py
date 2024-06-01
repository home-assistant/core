"""Test the init file code."""

from unittest.mock import patch

import pytest
from zeversolar import StatusEnum, ZeverSolarData
from zeversolar.exceptions import ZeverSolarTimeout

import homeassistant.components.zeversolar.__init__ as init
from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry

MOCK_HOST_ZEVERSOLAR = "zeversolar-fake-host"
MOCK_PORT_ZEVERSOLAR = 10200

MOCK_DATA = ZeverSolarData(
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


def create_config_mock():
    """Create a mock config entry."""

    return MockConfigEntry(
        data={
            CONF_HOST: MOCK_HOST_ZEVERSOLAR,
            CONF_PORT: MOCK_PORT_ZEVERSOLAR,
        },
        domain=DOMAIN,
        unique_id="my_id_2",
    )


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry."""

    config = create_config_mock()
    config.add_to_hass(hass)

    with (
        patch("zeversolar.ZeverSolarClient.get_data", return_value=MOCK_DATA),
    ):
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is True


async def test_async_setup_entry_fails(hass: HomeAssistant) -> None:
    """Test to start the integration when inverter is offline (e.g. at night)."""

    config = create_config_mock()
    config.add_to_hass(hass)

    with (
        patch(
            "zeversolar.ZeverSolarClient.get_data",
            side_effect=ZeverSolarTimeout,
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await init.async_setup_entry(hass, config)


async def test_load_entry(
    hass: HomeAssistant,
) -> None:
    """Test loading the entry."""

    with (
        patch("homeassistant.components.zeversolar.PLATFORMS", [Platform.SENSOR]),
        patch("zeversolar.ZeverSolarClient.get_data", return_value=MOCK_DATA),
    ):
        entry = create_config_mock()
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
