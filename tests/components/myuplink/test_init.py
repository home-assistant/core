"""Tests for init module."""

from datetime import timedelta
import http
import time
from typing import Any
from unittest.mock import MagicMock, patch

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
import orjson
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_fixture,
)
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.myuplink.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.setup import async_setup_component

from . import setup_integration
from .const import UNIQUE_ID


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_oauth2_implementation_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test OAuth2 implementation unavailable error."""

    mock_config_entry.add_to_hass(hass)

    with patch(
        f"homeassistant.components.{DOMAIN}.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("expires_at", "status", "expected_state"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["unauthorized", "internal_server_error"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=status,
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    ("expires_at", "expected_state"),
    [
        (
            time.time() - 3600,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=[
        "client_connection_error",
    ],
)
async def test_expired_token_refresh_connection_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a ClientError."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        exc=ClientConnectionError(),
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    "load_systems_file",
    [load_fixture("systems.json", DOMAIN)],
)
async def test_devices_created_count(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that one device is created."""
    await setup_integration(hass, mock_config_entry)

    assert len(device_registry.devices) == 1


async def test_devices_multiple_created_count(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that multiple devices are created."""
    await setup_integration(hass, mock_config_entry)

    assert len(device_registry.devices) == 2


async def test_migrate_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_myuplink_client: MagicMock,
    expires_at: float,
    access_token: str,
) -> None:
    """Test migration of config entry."""
    mock_entry_v1_1 = MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="myUplink test",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": access_token,
                "scope": "WRITESYSTEM READSYSTEM offline_access",
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "token_type": "Bearer",
                "expires_at": expires_at,
            },
        },
        entry_id="myuplink_test",
    )

    await setup_integration(hass, mock_entry_v1_1)
    assert mock_entry_v1_1.version == 1
    assert mock_entry_v1_1.minor_version == 2
    assert mock_entry_v1_1.unique_id == UNIQUE_ID


async def test_oaut2_scope_failure(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an incorrect OAuth2 scope fails."""

    mock_config_entry.data["token"]["scope"] = "wrong_scope"
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_device_remove_devices(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_myuplink_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (
            DOMAIN,
            "batman-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff",
        ),
        mock_config_entry.entry_id,
    )
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id)
    assert not response["success"]

    old_device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "OLD-DEVICE-UUID")},
    )
    response = await client.remove_device(old_device_entry.id)
    assert response["success"]


@pytest.mark.parametrize(
    "load_systems_file",
    [load_fixture("systems-multi.json", DOMAIN)],
    ids=[
        "multi",
    ],
)
@pytest.mark.parametrize(
    ("load_device_file", "device_id"),
    [
        (
            load_fixture("device-alfred.json", DOMAIN),
            "alfred-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff",
        ),
        (
            load_fixture("device-batman.json", DOMAIN),
            "batman-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff",
        ),
        (
            load_fixture("device-robin.json", DOMAIN),
            "robin-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff",
        ),
    ],
    ids=[
        "alfred",
        "batman",
        "robin",
    ],
)
async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    device_id: str,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.parametrize(
    ("platforms", "entity_id"),
    [
        pytest.param(
            [Platform.BINARY_SENSOR],
            "binary_sensor.gotham_city_pump_heating_medium_gp1",
            id="binary_sensor",
        ),
        pytest.param(
            [Platform.NUMBER],
            "number.gotham_city_heating_offset_climate_system_1",
            id="number",
        ),
        pytest.param([Platform.SELECT], "select.gotham_city_comfort_mode", id="select"),
        pytest.param(
            [Platform.SENSOR], "sensor.gotham_city_int_elec_add_heat", id="enum_sensor"
        ),
        pytest.param(
            [Platform.SWITCH], "switch.gotham_city_temporary_lux", id="switch"
        ),
    ],
)
async def test_entity_unknown_when_point_is_missing(
    hass: HomeAssistant,
    mock_myuplink_client: MagicMock,
    setup_platform: None,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    entity_id: str,
) -> None:
    """Test an entity is unknown when an update is missing its data point."""
    assert (state := hass.states.get(entity_id))
    assert state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)

    mock_myuplink_client.async_get_device_points.return_value = []
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN
    assert "Unexpected error" not in caplog.text


def _s320_point(parameter_id: str, name: str, **overrides: Any) -> dict[str, Any]:
    """Return a writable data point as a NIBE S320 reports it."""
    return {
        "category": "NIBE VVM S320 CU EM 3x400V",
        "parameterId": parameter_id,
        "parameterName": name,
        "parameterUnit": "",
        "writable": True,
        "timestamp": "2026-11-20T10:00:00+00:00",
        "value": 0.0,
        "strVal": "0",
        "smartHomeCategories": [],
        "minValue": None,
        "maxValue": None,
        "stepValue": 1.0,
        "enumValues": [],
        "scaleValue": "1",
        "zoneId": None,
    } | overrides


@pytest.mark.parametrize(
    "load_device_points_jv_file",
    [
        orjson.dumps(
            [
                _s320_point("47007", "Heating curve", minValue=0.0, maxValue=15.0),
                _s320_point(
                    "10613", "Activate SG Ready via API", minValue=0.0, maxValue=1.0
                ),
                _s320_point(
                    "61597",
                    "Public Rest API Enabled",
                    category="Software Debug",
                    minValue=0.0,
                    maxValue=1.0,
                ),
                _s320_point(
                    "61999",
                    "Debug log level",
                    category="Software Debug",
                    minValue=0.0,
                    maxValue=5.0,
                ),
            ]
        ).decode()
    ],
)
async def test_settings_with_zero_limit(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_myuplink_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that settings with a limit of 0 can be changed, with the right range."""
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()
    device_id = "robin-r-1234-20240201-123456-aa-bb-cc-dd-ee-ff"

    assert not entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{device_id}-47007"
    )
    entity_id = entity_registry.async_get_entity_id(
        Platform.NUMBER, DOMAIN, f"{device_id}-47007"
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 15

    assert not entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{device_id}-10613"
    )
    assert entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{device_id}-10613"
    )

    # Settings for the unit itself, like its local API, start disabled
    for platform, point_id in ((Platform.SWITCH, "61597"), (Platform.NUMBER, "61999")):
        entity_id = entity_registry.async_get_entity_id(
            platform, DOMAIN, f"{device_id}-{point_id}"
        )
        assert entity_id
        entry = entity_registry.async_get(entity_id)
        assert entry
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert entry.entity_category is EntityCategory.CONFIG
