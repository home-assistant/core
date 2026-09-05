"""Focused unit tests for Ecobulles sensor internals."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.ecobulles.const import DOMAIN
from homeassistant.components.ecobulles.coordinator import (
    EcobullesCoordinator,
    EcobullesData,
)
from homeassistant.components.ecobulles.sensor import (
    SENSORS,
    EcobullesSensor,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

pytestmark = pytest.mark.asyncio


def _usage(total_eau: int = 100, total_gas: int = 150_000) -> dict:
    """Return a minimal usage payload."""
    return {
        "total_eau": total_eau,
        "total_gas": total_gas,
        "last_updated": "2026-05-21T00:17:58",
    }


def _coordinator(
    hass: HomeAssistant, mock_config_entry, api=None
) -> EcobullesCoordinator:
    """Build a coordinator with mocked API."""
    return EcobullesCoordinator(
        hass,
        api
        or SimpleNamespace(
            get_total_water_and_co2_usage=AsyncMock(return_value=_usage()),
        ),
        mock_config_entry,
    )


async def test_sensor_setup(hass: HomeAssistant, mock_config_entry) -> None:
    """Sensor setup creates the Ecobulles sensors."""
    mock_config_entry.runtime_data = _coordinator(hass, mock_config_entry)
    add_entities = MagicMock()

    # pylint: disable-next=home-assistant-tests-direct-platform-async-setup-entry
    await async_setup_entry(hass, mock_config_entry, add_entities)

    unique_ids = {entity.unique_id for entity in add_entities.call_args.args[0]}
    assert unique_ids == {
        "test-eco-ref_water_usage",
        "test-eco-ref_co2_injection_time",
    }


async def test_coordinator_update_success(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Coordinator exposes usage as typed runtime data."""
    coordinator = _coordinator(
        hass,
        mock_config_entry,
        api=SimpleNamespace(
            get_total_water_and_co2_usage=AsyncMock(
                return_value=_usage(total_eau=7, total_gas=1500)
            ),
        ),
    )

    data = await coordinator._async_update_data()

    assert data == EcobullesData(
        water_liters=7,
        co2_injection_time_seconds=1.5,
        last_updated="2026-05-21T00:17:58",
    )


async def test_coordinator_update_fails_on_incomplete_payload(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Incomplete required API payloads mark the update as failed."""
    coordinator = _coordinator(
        hass,
        mock_config_entry,
        api=SimpleNamespace(get_total_water_and_co2_usage=AsyncMock(return_value=None)),
    )

    with pytest.raises(UpdateFailed, match="api_payload_incomplete"):
        await coordinator._async_update_data()

    partial_payload_coordinator = _coordinator(
        hass,
        mock_config_entry,
        api=SimpleNamespace(
            get_total_water_and_co2_usage=AsyncMock(return_value={"total_gas": 1})
        ),
    )
    with pytest.raises(UpdateFailed, match="api_payload_incomplete"):
        await partial_payload_coordinator._async_update_data()


async def test_coordinator_update_wraps_timeout_and_runtime_errors(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Coordinator failures are normalized to UpdateFailed."""
    timeout_coordinator = _coordinator(
        hass,
        mock_config_entry,
        api=SimpleNamespace(
            get_total_water_and_co2_usage=AsyncMock(side_effect=TimeoutError)
        ),
    )
    with pytest.raises(UpdateFailed, match="cannot_connect"):
        await timeout_coordinator._async_update_data()

    failing_coordinator = _coordinator(
        hass,
        mock_config_entry,
        api=SimpleNamespace(
            get_total_water_and_co2_usage=AsyncMock(side_effect=RuntimeError("boom"))
        ),
    )
    with pytest.raises(UpdateFailed, match="update_error"):
        await failing_coordinator._async_update_data()


async def test_sensor_native_values(hass: HomeAssistant, mock_config_entry) -> None:
    """Sensor classes expose their values."""
    coordinator = _coordinator(hass, mock_config_entry)
    coordinator.async_set_updated_data(
        EcobullesData(
            water_liters=42,
            co2_injection_time_seconds=1.5,
            last_updated="2026-05-21T00:17:58",
        )
    )

    sensors = {
        description.key: EcobullesSensor(coordinator, "eco-ref", description)
        for description in SENSORS
    }

    assert sensors["water_usage"].native_value == 42
    assert sensors["co2_injection_time"].native_value == 1.5
    assert sensors["water_usage"].device_info == {"identifiers": {(DOMAIN, "eco-ref")}}
