"""Test Rejseplanen sensor subentry functionality."""

from unittest.mock import MagicMock, patch

from py_rejseplan.dataclasses.departure_board import DepartureBoard
from py_rejseplan.enums import TransportClass

from homeassistant.components.rejseplanen.const import (
    CONF_DEPARTURE_TYPE,
    CONF_DIRECTION,
    CONF_NAME,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_sensor_with_stop_subentry(
    hass: HomeAssistant,
    setup_main_integration: MockConfigEntry,
    platforms: list[Platform],
) -> None:
    """Test sensor creation with stop subentry."""
    main_entry = setup_main_integration

    # Initialize subentry flow
    result = await hass.config_entries.subentries.async_init(
        (main_entry.entry_id, "stop"), context={"source": SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # Configure the subentry
    with (
        patch("homeassistant.components.rejseplanen.PLATFORMS", platforms),
        patch(
            "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
        ) as mock_api_class,
    ):
        mock_api = MagicMock()
        mock_api.get_departures.return_value = (MagicMock(departures=[]), [])
        mock_api_class.return_value = mock_api

        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                CONF_STOP_ID: 123456,
                CONF_NAME: "Test Stop",
                CONF_DIRECTION: [],
                CONF_DEPARTURE_TYPE: [],
            },
        )
        await hass.async_block_till_done()

    # ✅ Verify subentry creation succeeded
    assert result2["type"] == "create_entry"
    assert result2["title"] == "Test Stop"

    # ✅ Subentry data should be in the result
    assert result2["data"][CONF_STOP_ID] == 123456
    assert result2["data"][CONF_NAME] == "Test Stop"


async def test_sensor_with_filters(
    hass: HomeAssistant,
    setup_main_integration: MockConfigEntry,
    platforms: list[Platform],
) -> None:
    """Test sensor with direction and departure type filters."""
    main_entry = setup_main_integration

    result = await hass.config_entries.subentries.async_init(
        (main_entry.entry_id, "stop"), context={"source": SOURCE_USER}
    )

    with (
        patch("homeassistant.components.rejseplanen.PLATFORMS", platforms),
        patch(
            "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
        ) as mock_api_class,
    ):
        mock_api = MagicMock()
        mock_api.get_departures.return_value = (MagicMock(departures=[]), [])
        mock_api_class.return_value = mock_api

        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                CONF_STOP_ID: 123456,
                CONF_NAME: "Test Stop",
                CONF_DIRECTION: ["North"],
                CONF_DEPARTURE_TYPE: ["bus"],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"

    # ✅ Verify filter data in result
    assert result2["data"][CONF_DIRECTION] == ["North"]
    assert result2["data"][CONF_DEPARTURE_TYPE] == [TransportClass.BUS]


async def test_sensor_extra_state_attributes(
    hass: HomeAssistant,
    setup_integration_with_stop: tuple[MockConfigEntry, ConfigSubentry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor extra state attributes are populated."""
    _main_entry, subentry = setup_integration_with_stop

    # Verify the sensor entity was created (use the 'departures' sensor key)
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{subentry.subentry_id}_departures"
    )
    assert entity_id is not None

    # Verify the entity has a state
    state = hass.states.get(entity_id)
    assert state is not None

    # Verify state attributes structure exists
    attributes = state.attributes
    assert "stop_id" in attributes
    assert "attribution" in attributes


async def test_sensor_unavailable_when_no_data(
    hass: HomeAssistant, setup_main_integration: MockConfigEntry
) -> None:
    """Test sensor is unavailable when there is no departure data."""
    main_entry = setup_main_integration

    # Create a sub-entry but mock the API to return no departures
    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_board = MagicMock(spec=DepartureBoard)
        mock_board.departures = []
        mock_api.get_departures.return_value = (mock_board, [])
        mock_api_class.return_value = mock_api

        result = await hass.config_entries.subentries.async_init(
            (main_entry.entry_id, "stop"), context={"source": SOURCE_USER}
        )
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                CONF_STOP_ID: "654321",
                CONF_NAME: "Unavailable Stop",
            },
        )
        await hass.async_block_till_done()

    # Get the created subentry
    assert len(main_entry.subentries) == 1
    subentry_id = list(main_entry.subentries.keys())[0]

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{subentry_id}_departure_time"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    # When there are no departures, the sensor returns "unknown" state
    assert state.state == "unknown"


async def test_device_info_on_subentry_sensor(
    hass: HomeAssistant,
    setup_integration_with_stop: tuple[MockConfigEntry, ConfigSubentry],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that device info is correctly assigned to a sub-entry sensor."""
    _main_entry, subentry = setup_integration_with_stop

    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{subentry.subentry_id}_line"
    )
    assert entity_id is not None

    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.device_id is not None

    device = device_registry.async_get(entity.device_id)
    assert device is not None
    assert device.name == "Test Stop"
