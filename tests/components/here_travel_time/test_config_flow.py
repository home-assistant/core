"""Test the HERE Travel Time config flow."""
from unittest.mock import MagicMock, patch

from herepy.routing_api import InvalidCredentialsError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.here_travel_time.const import (
    ARRIVAL_TIME,
    CONF_ARRIVAL,
    CONF_DEPARTURE,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_ROUTE_MODE,
    CONF_TIME,
    CONF_TIME_TYPE,
    CONF_TRAFFIC_MODE,
    DEPARTURE_TIME,
    DOMAIN,
    ROUTE_MODE_FASTEST,
    TRAFFIC_MODE_ENABLED,
    TRAVEL_MODE_CAR,
)
from homeassistant.components.here_travel_time.sensor import (
    CONF_DESTINATION_ENTITY_ID,
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_ORIGIN_ENTITY_ID,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import HomeAssistant

from .const import (
    API_KEY,
    CAR_DESTINATION_LATITUDE,
    CAR_DESTINATION_LONGITUDE,
    CAR_ORIGIN_LATITUDE,
    CAR_ORIGIN_LONGITUDE,
)

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "herepy.RoutingApi.public_transport_timetable",
        return_value=None,
    ), patch(
        "homeassistant.components.here_travel_time.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ORIGIN: f"{CAR_ORIGIN_LATITUDE},{CAR_ORIGIN_LONGITUDE}",
                CONF_DESTINATION: f"{CAR_DESTINATION_LATITUDE},{CAR_DESTINATION_LONGITUDE}",
                CONF_API_KEY: API_KEY,
                CONF_MODE: TRAVEL_MODE_CAR,
                CONF_NAME: "test",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test"
    assert result2["data"] == {
        CONF_ORIGIN: f"{CAR_ORIGIN_LATITUDE},{CAR_ORIGIN_LONGITUDE}",
        CONF_DESTINATION: f"{CAR_DESTINATION_LATITUDE},{CAR_DESTINATION_LONGITUDE}",
        CONF_API_KEY: API_KEY,
        CONF_MODE: TRAVEL_MODE_CAR,
        CONF_NAME: "test",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "herepy.RoutingApi.public_transport_timetable",
        side_effect=InvalidCredentialsError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ORIGIN: f"{CAR_ORIGIN_LATITUDE},{CAR_ORIGIN_LONGITUDE}",
                CONF_DESTINATION: f"{CAR_DESTINATION_LATITUDE},{CAR_DESTINATION_LONGITUDE}",
                CONF_API_KEY: API_KEY,
                CONF_MODE: TRAVEL_MODE_CAR,
                CONF_NAME: "test",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "herepy.RoutingApi.public_transport_timetable",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ORIGIN: f"{CAR_ORIGIN_LATITUDE},{CAR_ORIGIN_LONGITUDE}",
                CONF_DESTINATION: f"{CAR_DESTINATION_LATITUDE},{CAR_DESTINATION_LONGITUDE}",
                CONF_API_KEY: API_KEY,
                CONF_MODE: TRAVEL_MODE_CAR,
                CONF_NAME: "test",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_options_flow(hass: HomeAssistant, valid_response: MagicMock) -> None:
    """Test the options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0123456789",
        data={
            CONF_ORIGIN: f"{CAR_ORIGIN_LATITUDE},{CAR_ORIGIN_LONGITUDE}",
            CONF_DESTINATION: f"{CAR_DESTINATION_LATITUDE},{CAR_DESTINATION_LONGITUDE}",
            CONF_API_KEY: API_KEY,
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_NAME: "test",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_TIME_TYPE: DEPARTURE_TIME,
            CONF_TIME: "",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert entry.options == {
        CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
        CONF_TIME_TYPE: DEPARTURE_TIME,
        CONF_TIME: None,
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
    }


async def test_import_flow_entity_id(
    hass: HomeAssistant, valid_response: MagicMock
) -> None:
    """Test import_flow with entity ids."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: CONF_API_KEY,
            CONF_ORIGIN_ENTITY_ID: "sensor.origin",
            CONF_DESTINATION_ENTITY_ID: "sensor.destination",
            CONF_NAME: "test_name",
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_DEPARTURE: "08:00:00",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test_name"

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {
        CONF_NAME: "test_name",
        CONF_API_KEY: CONF_API_KEY,
        CONF_ORIGIN: "sensor.origin",
        CONF_DESTINATION: "sensor.destination",
        CONF_MODE: TRAVEL_MODE_CAR,
    }
    assert entry.options == {
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
        CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        CONF_TIME_TYPE: DEPARTURE_TIME,
        CONF_TIME: "08:00:00",
    }


async def test_import_flow_coordinates(
    hass: HomeAssistant, valid_response: MagicMock
) -> None:
    """Test import_flow with coordinates."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: CONF_API_KEY,
            CONF_ORIGIN_LATITUDE: CAR_ORIGIN_LATITUDE,
            CONF_ORIGIN_LONGITUDE: CAR_ORIGIN_LONGITUDE,
            CONF_DESTINATION_LATITUDE: CAR_DESTINATION_LATITUDE,
            CONF_DESTINATION_LONGITUDE: CAR_DESTINATION_LONGITUDE,
            CONF_NAME: "test_name",
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_ARRIVAL: "08:00:00",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test_name"

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {
        CONF_NAME: "test_name",
        CONF_API_KEY: CONF_API_KEY,
        CONF_ORIGIN: f"{CAR_ORIGIN_LATITUDE},{CAR_ORIGIN_LONGITUDE}",
        CONF_DESTINATION: f"{CAR_DESTINATION_LATITUDE},{CAR_DESTINATION_LONGITUDE}",
        CONF_MODE: TRAVEL_MODE_CAR,
    }
    assert entry.options == {
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
        CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
        CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        CONF_TIME_TYPE: ARRIVAL_TIME,
        CONF_TIME: "08:00:00",
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
    }


async def test_dupe_import(hass: HomeAssistant, valid_response: MagicMock) -> None:
    """Test duplicate import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: CONF_API_KEY,
            CONF_ORIGIN_LATITUDE: CAR_ORIGIN_LATITUDE,
            CONF_ORIGIN_LONGITUDE: CAR_ORIGIN_LONGITUDE,
            CONF_DESTINATION_LATITUDE: CAR_DESTINATION_LATITUDE,
            CONF_DESTINATION_LONGITUDE: CAR_DESTINATION_LONGITUDE,
            CONF_NAME: "test_name",
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_ARRIVAL: "08:00:00",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: CONF_API_KEY,
            CONF_ORIGIN_LATITUDE: CAR_ORIGIN_LATITUDE,
            CONF_ORIGIN_LONGITUDE: CAR_ORIGIN_LONGITUDE,
            CONF_DESTINATION_LATITUDE: CAR_DESTINATION_LATITUDE,
            CONF_DESTINATION_LONGITUDE: CAR_DESTINATION_LONGITUDE,
            CONF_NAME: "test_name2",
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_ARRIVAL: "08:00:00",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: CONF_API_KEY,
            CONF_ORIGIN_LATITUDE: CAR_ORIGIN_LATITUDE,
            CONF_ORIGIN_LONGITUDE: CAR_ORIGIN_LONGITUDE,
            CONF_DESTINATION_LATITUDE: CAR_DESTINATION_LATITUDE,
            CONF_DESTINATION_LONGITUDE: CAR_DESTINATION_LONGITUDE,
            CONF_NAME: "test_name",
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_ARRIVAL: "08:00:01",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: CONF_API_KEY,
            CONF_ORIGIN_LATITUDE: CAR_ORIGIN_LATITUDE,
            CONF_ORIGIN_LONGITUDE: CAR_ORIGIN_LONGITUDE,
            CONF_DESTINATION_LATITUDE: CAR_DESTINATION_LATITUDE,
            CONF_DESTINATION_LONGITUDE: CAR_DESTINATION_LONGITUDE,
            CONF_NAME: "test_name",
            CONF_MODE: TRAVEL_MODE_CAR,
            CONF_ARRIVAL: "08:00:00",
            CONF_ROUTE_MODE: ROUTE_MODE_FASTEST,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            CONF_TRAFFIC_MODE: TRAFFIC_MODE_ENABLED,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
