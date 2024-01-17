"""The serive tests for the tado platform."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components.tado.const import (
    ATTR_CONFIG_ENTRY,
    ATTR_READING,
    DOMAIN,
    SERVICE_ADD_METER_READING,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .util import async_init_integration

from tests.common import MockConfigEntry, load_fixture


async def test_has_services(
    hass: HomeAssistant,
) -> None:
    """Test the existence of the Tado Service."""

    await async_init_integration(hass)

    assert hass.services.has_service(DOMAIN, SERVICE_ADD_METER_READING)


async def test_add_meter_readings(
    hass: HomeAssistant,
) -> None:
    """Test the add_meter_readings service."""

    await async_init_integration(hass)

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    fixture: str = load_fixture("tado/add_readings_success.json")
    with patch(
        "homeassistant.components.tado.TadoConnector.set_meter_reading",
        return_value=json.loads(fixture),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_METER_READING,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                ATTR_READING: 1234,
            },
            blocking=True,
        )


async def test_add_meter_readings_exception(
    hass: HomeAssistant,
) -> None:
    """Test the add_meter_readings service with a None response (generic RequestExceptionwas raised)."""

    await async_init_integration(hass)

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    with (
        patch(
            "homeassistant.components.tado.TadoConnector.set_meter_reading",
            return_value=None,
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_METER_READING,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                ATTR_READING: 1234,
            },
            blocking=True,
        )


async def test_add_meter_readings_invalid(
    hass: HomeAssistant,
) -> None:
    """Test the add_meter_readings service with an invalid_meter_reading response."""

    await async_init_integration(hass)

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    fixture: str = load_fixture("tado/add_readings_invalid_meter_reading.json")
    with (
        patch(
            "homeassistant.components.tado.TadoConnector.set_meter_reading",
            return_value=json.loads(fixture),
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_METER_READING,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                ATTR_READING: 1234,
            },
            blocking=True,
        )


async def test_add_meter_readings_duplicate(
    hass: HomeAssistant,
) -> None:
    """Test the add_meter_readings service with a duplicated_meter_reading response."""

    await async_init_integration(hass)

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    fixture: str = load_fixture("tado/add_readings_duplicated_meter_reading.json")
    with (
        patch(
            "homeassistant.components.tado.TadoConnector.set_meter_reading",
            return_value=json.loads(fixture),
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_METER_READING,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                ATTR_READING: 1234,
            },
            blocking=True,
        )
