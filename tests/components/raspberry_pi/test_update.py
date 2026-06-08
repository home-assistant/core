"""Test the Raspberry Pi firmware update entity."""

from unittest.mock import AsyncMock, patch

from aiohasupervisor import SupervisorNotFoundError
from aiohasupervisor.models import RaspberryPiFirmwareInfo
import pytest

from homeassistant.components.hassio import DOMAIN as HASSIO_DOMAIN
from homeassistant.components.raspberry_pi.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration

RPI_FIRMWARE_ENTITY_ID = "update.raspberry_pi_5_firmware"


@pytest.fixture(autouse=True)
def mock_rpi_power():
    """Mock the rpi_power integration."""
    with patch(
        "homeassistant.components.rpi_power.async_setup_entry",
        return_value=True,
    ):
        yield


async def _setup_rpi(hass: HomeAssistant, board: str) -> None:
    """Set up the raspberry_pi config entry on a given board."""
    mock_integration(hass, MockModule("hassio"))
    await async_setup_component(hass, HASSIO_DOMAIN, {})

    config_entry = MockConfigEntry(data={}, domain=DOMAIN, title="Raspberry Pi")
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.raspberry_pi.get_os_info",
            return_value={"board": board},
        ),
        patch(
            "homeassistant.components.raspberry_pi.update.get_os_info",
            return_value={"board": board},
        ),
        patch("homeassistant.components.rpi_power.config_flow.new_under_voltage"),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_rpi_firmware_update_entity(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> None:
    """The firmware update entity is created on its own RPi board device."""
    supervisor_client.os.raspberry_pi_firmware_info.return_value = (
        RaspberryPiFirmwareInfo(
            current_version="1765222194",
            latest_version="1778498402",
            update_available=True,
            update_blocked=False,
            update_pending=False,
            blocked_reason=None,
        )
    )
    await _setup_rpi(hass, "rpi5-64")

    state = hass.states.get(RPI_FIRMWARE_ENTITY_ID)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["installed_version"] == "2025-12-08"
    assert state.attributes["latest_version"] == "2026-05-11"


async def test_rpi_firmware_entity_absent_on_older_supervisor(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> None:
    """No entity when the Supervisor doesn't expose the endpoint (404)."""
    supervisor_client.os.raspberry_pi_firmware_info.side_effect = (
        SupervisorNotFoundError("Not found")
    )
    await _setup_rpi(hass, "rpi5-64")

    assert hass.states.get(RPI_FIRMWARE_ENTITY_ID) is None


async def test_rpi_firmware_entity_absent_on_unsupported_board(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> None:
    """No entity (or firmware probe) on boards without an EEPROM bootloader."""
    await _setup_rpi(hass, "rpi3-64")

    assert hass.states.get(RPI_FIRMWARE_ENTITY_ID) is None
    supervisor_client.os.raspberry_pi_firmware_info.assert_not_called()
