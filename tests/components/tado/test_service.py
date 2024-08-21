"""The serive tests for the tado platform."""

import json
from unittest.mock import patch

import pytest
from requests.exceptions import RequestException

from homeassistant.components.tado.const import (
    CONF_CONFIG_ENTRY,
    CONF_READING,
    DOMAIN,
    SERVICE_ADD_METER_READING,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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
        "PyTado.interface.Tado.set_eiq_meter_readings",
        return_value=json.loads(fixture),
    ):
        response: None = await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_METER_READING,
            service_data={
                CONF_CONFIG_ENTRY: config_entry.entry_id,
                CONF_READING: 1234,
            },
            blocking=True,
        )
        assert response is None


async def test_add_meter_readings_exception(
    hass: HomeAssistant,
) -> None:
    """Test the add_meter_readings service with a RequestException."""

    await async_init_integration(hass)

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    with (
        patch(
            "PyTado.interface.Tado.set_eiq_meter_readings",
            side_effect=RequestException("Error"),
        ),
        pytest.raises(HomeAssistantError) as exc,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_METER_READING,
            service_data={
                CONF_CONFIG_ENTRY: config_entry.entry_id,
                CONF_READING: 1234,
            },
            blocking=True,
        )

    assert "Could not set meter reading" in str(exc)


async def test_add_meter_readings_invalid(
    hass: HomeAssistant,
) -> None:
    """Test the add_meter_readings service with an invalid_meter_reading response."""

    await async_init_integration(hass)

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    fixture: str = load_fixture("tado/add_readings_invalid_meter_reading.json")
    with (
        patch(
            "PyTado.interface.Tado.set_eiq_meter_readings",
            return_value=json.loads(fixture),
        ),
        pytest.raises(HomeAssistantError) as exc,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_METER_READING,
            service_data={
                CONF_CONFIG_ENTRY: config_entry.entry_id,
                CONF_READING: 1234,
            },
            blocking=True,
        )

    assert "invalid new reading" in str(exc)


async def test_add_meter_readings_duplicate(
    hass: HomeAssistant,
) -> None:
    """Test the add_meter_readings service with a duplicated_meter_reading response."""

    await async_init_integration(hass)

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    fixture: str = load_fixture("tado/add_readings_duplicated_meter_reading.json")
    with (
        patch(
            "PyTado.interface.Tado.set_eiq_meter_readings",
            return_value=json.loads(fixture),
        ),
        pytest.raises(HomeAssistantError) as exc,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_METER_READING,
            service_data={
                CONF_CONFIG_ENTRY: config_entry.entry_id,
                CONF_READING: 1234,
            },
            blocking=True,
        )

    assert "reading already exists for date" in str(exc)
