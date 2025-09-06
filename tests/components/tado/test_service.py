"""The serive tests for the tado platform."""

from unittest.mock import AsyncMock

import pytest
from tadoasync import TadoReadingError

from homeassistant.components.tado.const import (
    CONF_CONFIG_ENTRY,
    CONF_READING,
    DOMAIN,
    SERVICE_ADD_METER_READING,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_tado_api")
async def test_has_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the existence of the Tado Service."""

    await setup_integration(hass, mock_config_entry)

    assert hass.services.has_service(DOMAIN, SERVICE_ADD_METER_READING)


async def test_add_meter_readings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tado_api: AsyncMock,
) -> None:
    """Test the add_meter_readings service."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_METER_READING,
        service_data={
            CONF_CONFIG_ENTRY: mock_config_entry.entry_id,
            CONF_READING: 1234,
        },
        blocking=True,
    )
    mock_tado_api.set_meter_readings.assert_called_once_with(1234)


async def test_add_meter_readings_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tado_api: AsyncMock,
) -> None:
    """Test the add_meter_readings service with a RequestException."""

    await setup_integration(hass, mock_config_entry)

    mock_tado_api.set_meter_readings.side_effect = TadoReadingError()

    with pytest.raises(HomeAssistantError, match="Error setting Tado meter reading:"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_METER_READING,
            {
                CONF_CONFIG_ENTRY: mock_config_entry.entry_id,
                CONF_READING: 1234,
            },
            blocking=True,
        )
