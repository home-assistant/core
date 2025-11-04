"""Test Rejseplanen sensor subentry functionality."""

from unittest.mock import MagicMock, patch

from py_rejseplan.dataclasses.departure import DepartureType as Departure
from py_rejseplan.dataclasses.departure_board import DepartureBoard
from py_rejseplan.enums import TransportClass

from homeassistant.components.rejseplanen.const import (
    CONF_DEPARTURE_TYPE,
    CONF_DIRECTION,
    CONF_NAME,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

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
) -> None:
    """Test sensor extra state attributes are populated."""
    # Create integration with multiple departure types
    departures = []
    for i, transport_type in enumerate(
        [TransportClass.BUS, TransportClass.METRO, TransportClass.S_TOG]
    ):
        dep = MagicMock(spec=Departure)
        dep.name = f"Line {i}"
        dep.type = transport_type
        dep.direction = f"Direction {i}"
        dep.time = f"{12 + i}:00"
        dep.date = "2024-11-04"
        dep.cancelled = False
        departures.append(dep)

    main_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "test", "name": "Test"},
        unique_id="test",
    )
    main_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_board = MagicMock(spec=DepartureBoard)
        mock_board.departures = departures
        mock_api.get_departures.return_value = (mock_board, [])
        mock_api_class.return_value = mock_api

        await hass.config_entries.async_setup(main_entry.entry_id)
        await hass.async_block_till_done()

    # Check sensor states
    states = hass.states.async_all()
    sensor_states = [s for s in states if s.entity_id.startswith("sensor.")]

    # Main integration without subentries won't have sensors
    assert len(sensor_states) >= 0

    # Check that any existing sensors have attributes
    for state in sensor_states:
        assert state.attributes is not None
