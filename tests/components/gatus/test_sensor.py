"""Tests for the Gatus sensor platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from gatus_api import EndpointStatus, Result
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    snapshot_platform,
)


async def test_sensor_setup_and_states(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test standard successful setup and entity snapshots using snapshot_platform."""
    freezer.move_to("2026-01-01 00:00:00+00:00")
    with patch("homeassistant.components.gatus._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


def _to_endpoint_statuses(raw_data: list[dict[str, Any]]) -> list[EndpointStatus]:
    return [
        EndpointStatus(
            key=ep["key"],
            name=ep["name"],
            group=ep.get("group"),
            results=[
                Result(
                    success=r["success"],
                    status=r.get("status"),
                    duration=r.get("duration"),
                    certificate_expiration=r.get("certificateExpiration"),
                    dns_rcode=r.get("dnsRcode"),
                )
                for r in ep.get("results", [])
            ],
        )
        for ep in raw_data
    ]


async def test_sensor_dynamic_update(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the sensor entity updates when the mock client returns new data."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("sensor.core_backend_service_response_time")
    assert state is not None
    assert state.state == "23.12"

    mock_data = await async_load_json_array_fixture(hass, "gatus/group.json")

    mock_gatus_client.get_endpoints_statuses.return_value = _to_endpoint_statuses(
        mock_data
    )

    freezer.tick(300)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.core_backend_service_response_time")
    assert state is not None
    assert state.state == "45.0"


async def test_sensor_no_group(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the sensor entity is created correctly when an endpoint has no group."""
    mock_data = await async_load_json_array_fixture(hass, "gatus/no_group.json")

    mock_gatus_client.get_endpoints_statuses.return_value = _to_endpoint_statuses(
        mock_data
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.backend_service_response_time")
    assert state is not None
    assert state.state == "12.5"


async def test_sensor_empty_results(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an endpoint with empty results is treated as unavailable."""
    mock_gatus_client.get_endpoints_statuses.return_value = [
        EndpointStatus(
            key="backend_service",
            name="Backend Service",
            group=None,
            results=[],
        )
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.backend_service_response_time")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_missing_duration(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a result missing duration evaluates to None for native_value."""
    mock_gatus_client.get_endpoints_statuses.return_value = [
        EndpointStatus(
            key="backend_service",
            name="Backend Service",
            group=None,
            results=[Result(success=True, status=200, duration=None)],
        )
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.backend_service_response_time")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_sensor_missing_status_code(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a result missing status code evaluates to STATE_UNKNOWN for status code sensor."""
    mock_gatus_client.get_endpoints_statuses.return_value = [
        EndpointStatus(
            key="backend_service",
            name="Backend Service",
            group=None,
            results=[Result(success=True, status=None, duration=12500000)],
        )
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.backend_service_status_code")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_sensor_missing_certificate_expiration(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a result missing certificate expiration creates no entity."""
    mock_gatus_client.get_endpoints_statuses.return_value = [
        EndpointStatus(
            key="backend_service",
            name="Backend Service",
            group=None,
            results=[
                Result(
                    success=True,
                    status=200,
                    duration=12500000,
                    certificate_expiration=None,
                )
            ],
        )
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.backend_service_certificate_expiration")
    assert state is None


async def test_sensor_missing_dns_rcode(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a result missing DNS rcode creates no entity."""
    mock_gatus_client.get_endpoints_statuses.return_value = [
        EndpointStatus(
            key="backend_service",
            name="Backend Service",
            group=None,
            results=[
                Result(
                    success=True,
                    status=200,
                    duration=12500000,
                    dns_rcode=None,
                )
            ],
        )
    ]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.backend_service_dns_response_code")
    assert state is None
