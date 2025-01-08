"""Test the Enphase Envoy services."""

from unittest.mock import AsyncMock, patch

from pyenphase import EnvoyError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import DOMAIN, Platform
from homeassistant.components.enphase_envoy.services import (
    ATTR_ENVOY,
    SERVICE_GET_FIRMWARE,
    SERVICE_LIST,
    setup_hass_services,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("mock_envoy"),
    [
        "envoy",
    ],
    indirect=["mock_envoy"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_has_services(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the existence of the Enphase Envoy Services."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    for service in SERVICE_LIST:
        assert hass.services.has_service(DOMAIN, service)
    assert snapshot == list(hass.services.async_services_for_domain(DOMAIN).keys())


async def test_service_load_unload(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test service loading and unlodig."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    # test with unloaded config entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    with pytest.raises(ServiceValidationError, match="service_not_found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_FIRMWARE,
            {ATTR_ENVOY: "envoy.1234"},
            blocking=True,
            return_response=True,
        )

    # test with simulated second loaded envoy for COV on envoylist handling
    with (
        patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]),
        patch.dict(
            "homeassistant.components.enphase_envoy.services.envoylist",
            {"4321": "hello world"},
        ),
    ):
        await setup_integration(hass, config_entry)
        assert config_entry.state is ConfigEntryState.LOADED

        # existing envoylist entry for COV of return in service setup
        await setup_hass_services(hass, config_entry)

        # existing envoylist entry for COV of return in service unload.
        await hass.config_entries.async_unload(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("service", "mock_envoy", "firmware", "service_data"),
    [
        (
            SERVICE_GET_FIRMWARE,
            "envoy",
            "7.6.175",
            {ATTR_ENVOY: "envoy.1234"},
        ),
        (
            SERVICE_GET_FIRMWARE,
            "envoy",
            "7.6.175",
            {ATTR_ENVOY: "sensor.envoy_1234_current_power_production"},
        ),
        (
            SERVICE_GET_FIRMWARE,
            "envoy",
            "7.6.175",
            {ATTR_ENVOY: "sensor.inverter_1"},
        ),
    ],
    indirect=["mock_envoy"],
)
async def test_service_get_firmware(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    service: str,
    firmware: str,
    service_data: dict[str, str],
) -> None:
    """Test service calls for get_firmware service."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.services.async_call(
        DOMAIN,
        service,
        service_data,
        blocking=True,
        return_response=True,
    )
    assert result["firmware"] == firmware
    assert result["previous_firmware"] == firmware

    mock_envoy.setup.side_effect = EnvoyError("Test")
    with pytest.raises(
        HomeAssistantError,
        match="Error in Envoy Service: get_firmware Test",
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            service_data,
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("service", "mock_envoy", "service_data"),
    [
        (
            SERVICE_GET_FIRMWARE,
            "envoy",
            {ATTR_ENVOY: "envoy.12345"},
        ),
        (
            SERVICE_GET_FIRMWARE,
            "envoy",
            {ATTR_ENVOY: "sensor.envoy_12345_current_power_production"},
        ),
        (
            SERVICE_GET_FIRMWARE,
            "envoy",
            {ATTR_ENVOY: "sensor.inverter_11"},
        ),
    ],
    indirect=["mock_envoy"],
)
async def test_service_get_firmware_exceptions(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    service: str,
    service_data: dict[str, str],
) -> None:
    """Test service calls for get_firmware service with faulty service data."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    with pytest.raises(
        ServiceValidationError,
        match=f"No Envoy found from serial or entity specified: get_firmware {service_data[ATTR_ENVOY]}",
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            service_data,
            blocking=True,
            return_response=True,
        )


# @pytest.mark.parametrize(
#     ("service", "mock_envoy", "service_data", "raw_key", "target"),
#     [
#         (
#             SERVICE_GET_LAST_DATA,
#             "envoy",
#             {ATTR_ENVOY: "envoy.1234", ATTR_ENDPOINT: ""},
#             "raw",
#             "RAW",
#         ),
#         (
#             SERVICE_GET_LAST_DATA,
#             "envoy",
#             {
#                 ATTR_ENVOY: "envoy.1234",
#                 ATTR_ENDPOINT: "/api/v1/production/inverters,1,maxReportWatts",
#             },
#             "maxReportWatts",
#             {"maxReportWatts": 248},
#         ),
#     ],
#     indirect=["mock_envoy"],
# )
# async def test_service_get_last_data(
#     hass: HomeAssistant,
#     mock_envoy: AsyncMock,
#     config_entry: MockConfigEntry,
#     service: str,
#     service_data: dict[str, str],
#     raw_key: str,
#     target: str | dict[str:str],
# ) -> None:
#     """Test service calls for get_last_data service."""
#     with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
#         await setup_integration(hass, config_entry)
#     assert config_entry.state is ConfigEntryState.LOADED

#     mock_envoy.data.raw = {
#         "/api/v1/production/inverters": [
#             {
#                 "serialNumber": "123456",
#                 "lastReportDate": 1735243251,
#                 "devType": 1,
#                 "lastReportWatts": 11,
#                 "maxReportWatts": 247,
#             },
#             {
#                 "serialNumber": "123457",
#                 "lastReportDate": 1735243251,
#                 "devType": 1,
#                 "lastReportWatts": 12,
#                 "maxReportWatts": 248,
#             },
#         ]
#     }

#     result = await hass.services.async_call(
#         DOMAIN,
#         service,
#         service_data,
#         blocking=True,
#         return_response=True,
#     )
#     assert result[raw_key] == mock_envoy.data.raw if target == "RAW" else target


# @pytest.mark.parametrize(
#     ("service", "mock_envoy", "service_data"),
#     [
#         (
#             SERVICE_GET_LAST_DATA,
#             "envoy",
#             {
#                 ATTR_ENVOY: "envoy.1234",
#                 ATTR_ENDPOINT: "/api/v1/production/inverters,3,maxReportWatts",
#             },
#         ),
#         (
#             SERVICE_GET_LAST_DATA,
#             "envoy",
#             {
#                 ATTR_ENVOY: "envoy.1234",
#                 ATTR_ENDPOINT: "/api/v1/production/inverters,1,MaxReportWatts",
#             },
#         ),
#     ],
#     indirect=["mock_envoy"],
# )
# async def test_service_get_last_data_exceptions(
#     hass: HomeAssistant,
#     mock_envoy: AsyncMock,
#     config_entry: MockConfigEntry,
#     service: str,
#     service_data: dict[str, str],
# ) -> None:
#     """Test service calls for get_last_data service with faulty service data."""
#     with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
#         await setup_integration(hass, config_entry)
#     assert config_entry.state is ConfigEntryState.LOADED

#     with pytest.raises(
#         ServiceValidationError,
#         match="Invalid parameters passed to Envoy service: get_last_data",
#     ):
#         await hass.services.async_call(
#             DOMAIN,
#             service,
#             service_data,
#             blocking=True,
#             return_response=True,
#         )

#     mock_envoy.data.raw = None

#     with pytest.raises(
#         ServiceValidationError,
#         match="get_last_data: Enphase envoy is not yet initialized",
#     ):
#         await hass.services.async_call(
#             DOMAIN,
#             service,
#             service_data,
#             blocking=True,
#             return_response=True,
#         )


# @pytest.mark.parametrize(
#     ("service", "mock_envoy", "service_data", "raw_key", "target"),
#     [
#         (
#             SERVICE_GET_CURRENT_DATA,
#             "envoy",
#             {
#                 ATTR_ENVOY: "envoy.1234",
#                 ATTR_ENDPOINT: "/api/v1/production/inverters",
#             },
#             "/api/v1/production/inverters",
#             (
#                 [
#                     {"hello": "world", "goodbye": "moon"},
#                     {"hello": "venus", "goodbye": "mars"},
#                 ]
#             ),
#         ),
#         (
#             SERVICE_GET_CURRENT_DATA,
#             "envoy",
#             {
#                 ATTR_ENVOY: "envoy.1234",
#                 ATTR_ENDPOINT: "/api/v1/production/inverters,1,goodbye",
#             },
#             "goodbye",
#             "mars",
#         ),
#     ],
#     indirect=["mock_envoy"],
# )
# async def test_service_get_current_data(
#     hass: HomeAssistant,
#     mock_envoy: AsyncMock,
#     config_entry: MockConfigEntry,
#     service: str,
#     service_data: dict[str, str],
#     raw_key: str,
#     target: str | dict[str:Any] | list[Any],
# ) -> None:
#     """Test service calls for get_current_data service."""
#     with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
#         await setup_integration(hass, config_entry)
#     assert config_entry.state is ConfigEntryState.LOADED

#     mock_envoy.request.return_value.content = (
#         '[{"hello": "world","goodbye":"moon"},{"hello": "venus","goodbye":"mars"}]'
#     )

#     result = await hass.services.async_call(
#         DOMAIN,
#         service,
#         service_data,
#         blocking=True,
#         return_response=True,
#     )
#     assert result[raw_key] == target


# @pytest.mark.parametrize(
#     ("service", "mock_envoy", "service_data"),
#     [
#         (
#             SERVICE_GET_CURRENT_DATA,
#             "envoy",
#             {
#                 ATTR_ENVOY: "envoy.1234",
#                 ATTR_ENDPOINT: "/api/v1/production/inverters,1,goodbye2",
#             },
#         ),
#     ],
#     indirect=["mock_envoy"],
# )
# async def test_service_get_current_data_exceptions(
#     hass: HomeAssistant,
#     mock_envoy: AsyncMock,
#     config_entry: MockConfigEntry,
#     service: str,
#     service_data: dict[str, str],
# ) -> None:
#     """Test service calls for get_current_data service exceptions."""
#     with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
#         await setup_integration(hass, config_entry)
#     assert config_entry.state is ConfigEntryState.LOADED

#     mock_envoy.request.return_value.content = (
#         '[{"hello": "world","goodbye":"moon"},{"hello": "venus","goodbye":"mars"}]'
#     )

#     with pytest.raises(
#         ServiceValidationError,
#         match="Invalid parameters passed to Envoy service: get_current_data goodbye2",
#     ):
#         await hass.services.async_call(
#             DOMAIN,
#             service,
#             service_data,
#             blocking=True,
#             return_response=True,
#         )

#     mock_envoy.request.return_value.content = bytes("Ok", "utf-8")

#     with pytest.raises(
#         ServiceValidationError,
#         match="Invalid parameters passed to Envoy service: get_current_data",
#     ):
#         await hass.services.async_call(
#             DOMAIN,
#             service,
#             service_data,
#             blocking=True,
#             return_response=True,
#         )

#     mock_envoy.request.return_value.status_code = 300

#     with pytest.raises(
#         HomeAssistantError,
#         match="Error in Envoy Service: get_current_data HTTP status error /api/v1/production/inverters 300",
#     ):
#         await hass.services.async_call(
#             DOMAIN,
#             service,
#             service_data,
#             blocking=True,
#             return_response=True,
#         )

#     mock_envoy.data = None

#     with pytest.raises(
#         HomeAssistantError,
#         match="get_current_data: Enphase envoy is not yet initialized",
#     ):
#         await hass.services.async_call(
#             DOMAIN,
#             service,
#             service_data,
#             blocking=True,
#             return_response=True,
#         )


# @pytest.mark.parametrize(
#     ("service", "mock_envoy", "service_data"),
#     [
#         (
#             SERVICE_POST_DATA,
#             "envoy",
#             {
#                 ATTR_ENVOY: "envoy.1234",
#                 ATTR_ENDPOINT: "/admin/lib/tariff",
#                 ATTR_JSON_DATA: '{"tariff": {"currency": {"code": "MOON"}}}',
#                 ATTR_METHOD: "",
#             },
#         )
#     ],
#     indirect=["mock_envoy"],
# )
# async def test_service_post_data(
#     hass: HomeAssistant,
#     mock_envoy: AsyncMock,
#     config_entry: MockConfigEntry,
#     service: str,
#     service_data: dict[str, str],
# ) -> None:
#     """Test service calls for post_data service."""
#     with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
#         await setup_integration(hass, config_entry)
#     assert config_entry.state is ConfigEntryState.LOADED

#     mock_envoy.request.return_value.content = service_data[ATTR_JSON_DATA]

#     result = await hass.services.async_call(
#         DOMAIN,
#         service,
#         service_data,
#         blocking=True,
#         return_response=True,
#     )
#     assert result[service_data[ATTR_ENDPOINT]] == orjson.loads(
#         service_data[ATTR_JSON_DATA]
#     )


# @pytest.mark.parametrize(
#     ("service", "mock_envoy", "service_data"),
#     [
#         (
#             SERVICE_POST_DATA,
#             "envoy",
#             {
#                 ATTR_ENVOY: "envoy.1234",
#                 ATTR_ENDPOINT: "/admin/lib/tariff",
#                 ATTR_JSON_DATA: '{tariff: {"currency": {"code": "MOON"}}}',
#                 ATTR_METHOD: "",
#             },
#         ),
#         (
#             SERVICE_POST_DATA,
#             "envoy",
#             {
#                 ATTR_ENVOY: "envoy.1234",
#                 ATTR_ENDPOINT: "/admin/lib/tariff",
#                 ATTR_JSON_DATA: '"{tariff: {"currency": {"code": "MOON"}}}"',
#                 ATTR_METHOD: "",
#             },
#         ),
#         (
#             SERVICE_POST_DATA,
#             "envoy",
#             {
#                 ATTR_ENVOY: "envoy.1234",
#                 ATTR_ENDPOINT: "/admin/lib/tariff",
#                 ATTR_JSON_DATA: '["hello","world"]',
#                 ATTR_METHOD: "",
#             },
#         ),
#     ],
#     indirect=["mock_envoy"],
# )
# async def test_service_post_data_invalid_parameters(
#     hass: HomeAssistant,
#     mock_envoy: AsyncMock,
#     config_entry: MockConfigEntry,
#     service: str,
#     service_data: dict[str, str],
# ) -> None:
#     """Test service calls for post_data service invalid parameters."""
#     with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
#         await setup_integration(hass, config_entry)
#     assert config_entry.state is ConfigEntryState.LOADED

#     with pytest.raises(
#         ServiceValidationError,
#         match="Invalid parameters passed to Envoy service: post_data",
#     ):
#         await hass.services.async_call(
#             DOMAIN,
#             service,
#             service_data,
#             blocking=True,
#             return_response=True,
#         )


# @pytest.mark.parametrize(
#     ("service", "mock_envoy", "service_data"),
#     [
#         (
#             SERVICE_POST_DATA,
#             "envoy",
#             {
#                 ATTR_ENVOY: "envoy.1234",
#                 ATTR_ENDPOINT: "/admin/lib/tariff",
#                 ATTR_JSON_DATA: '{"tariff": {"currency": {"code": "MOON"}}}',
#                 ATTR_METHOD: "",
#             },
#         )
#     ],
#     indirect=["mock_envoy"],
# )
# async def test_service_post_data_exceptions(
#     hass: HomeAssistant,
#     mock_envoy: AsyncMock,
#     config_entry: MockConfigEntry,
#     service: str,
#     service_data: dict[str, str],
# ) -> None:
#     """Test service calls for post_data service exceptions."""
#     with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.SENSOR]):
#         await setup_integration(hass, config_entry)
#     assert config_entry.state is ConfigEntryState.LOADED

#     mock_envoy.request.return_value.status_code = 300

#     with pytest.raises(
#         HomeAssistantError,
#         match="Error in Envoy Service: post_data HTTP status error /admin/lib/tariff 300",
#     ):
#         await hass.services.async_call(
#             DOMAIN,
#             service,
#             service_data,
#             blocking=True,
#             return_response=True,
#         )

#     mock_envoy.request.side_effect = EnvoyError("Test")
#     with pytest.raises(
#         HomeAssistantError,
#         match="Error communicating with Envoy API on",
#     ):
#         await hass.services.async_call(
#             DOMAIN,
#             service,
#             service_data,
#             blocking=True,
#             return_response=True,
#         )
