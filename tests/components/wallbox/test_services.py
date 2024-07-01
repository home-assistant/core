"""Tests for Wallbox services."""

import pytest
import requests_mock

from homeassistant.components.wallbox.const import CONF_STATION, DOMAIN
from homeassistant.components.wallbox.services import (
    ATTR_CHARGER_ID,
    ATTR_SCHEDULES,
    SERVICE_GET_SCHEDULES,
    SERVICE_SET_SCHEDULES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import authorisation_response, setup_integration

from tests.common import MockConfigEntry, load_fixture


async def test_service_get_schedules(
    hass: HomeAssistant, entry: MockConfigEntry, device_registry: dr.DeviceRegistry
) -> None:
    """Test that service invokes wallbox get schedules API with correct data and handles result conversion to local properly."""
    await setup_integration(hass, entry)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, CONF_STATION)},
    )

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.get(
            "https://api.wall-box.com/chargers/12345/schedules",
            text=load_fixture("wallbox/schedules.json"),
        )

        data = {ATTR_CHARGER_ID: CONF_STATION}

        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SCHEDULES,
            service_data=data,
            return_response=True,
            blocking=True,
        )

        first = result["schedules"][0]
        days = first["days"]
        assert first["start"] == "14:00"
        assert first["stop"] == "15:00"
        assert first["id"] == 0
        assert days["monday"] is True
        assert days["tuesday"] is True
        assert days["wednesday"] is True
        assert days["thursday"] is True
        assert days["friday"] is True
        assert days["saturday"] is True
        assert days["sunday"] is True
        assert first["max_current"] == 1
        assert first["max_energy"] == 0
        assert first["created_at"] == 1719136123


async def test_service_set_schedules(
    hass: HomeAssistant, entry: MockConfigEntry, device_registry: dr.DeviceRegistry
) -> None:
    """Test that service invokes wallbox set schedules API with correct data."""
    await setup_integration(hass, entry)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, CONF_STATION)},
    )

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.post(
            "https://api.wall-box.com/chargers/12345/schedules",
            text=load_fixture("wallbox/schedules.json"),
        )

        schedules = [
            {
                "id": 0,
                "start": "13:00",
                "stop": "14:00",
                "enable": True,
                "max_current": 0,
                "max_energy": 0,
                "days": {
                    "monday": True,
                    "tuesday": True,
                    "wednesday": True,
                    "thursday": True,
                    "friday": True,
                    "saturday": True,
                    "sunday": True,
                },
            },
        ]

        data = {
            ATTR_CHARGER_ID: CONF_STATION,
            ATTR_SCHEDULES: schedules,
        }

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_SCHEDULES,
            service_data=data,
            blocking=True,
        )


async def test_services_invalid_sn(
    hass: HomeAssistant, entry: MockConfigEntry, device_registry: dr.DeviceRegistry
) -> None:
    """Test that service raises exception if invalid serial is provided."""
    await setup_integration(hass, entry)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, CONF_STATION)},
    )

    with requests_mock.Mocker() as mock_request:
        mock_request.get(
            "https://user-api.wall-box.com/users/signin",
            json=authorisation_response,
            status_code=200,
        )
        mock_request.get(
            "https://api.wall-box.com/chargers/12345/schedules",
            text=load_fixture("wallbox/schedules.json"),
        )

        data = {ATTR_CHARGER_ID: "INVALID"}

        with pytest.raises(ValueError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_GET_SCHEDULES,
                service_data=data,
                return_response=True,
                blocking=True,
            )


async def test_services_load_and_unload(
    hass: HomeAssistant, entry: MockConfigEntry, device_registry: dr.DeviceRegistry
) -> None:
    """Test being able to unload an entry."""
    await setup_integration(hass, entry)

    services = hass.services.async_services()[DOMAIN]
    assert len(services) == 2

    await hass.config_entries.async_unload(entry.entry_id)
