"""Test the swiss_public_transport sensor."""
from unittest.mock import patch

from opendata_transport import OpendataTransport
import pytest

from homeassistant.components.swiss_public_transport.const import (
    ATTR_DELAY,
    ATTR_DEPARTURE_TIME1,
    ATTR_DEPARTURE_TIMES,
    CONF_DESTINATION,
    CONF_IS_ARRIVAL,
    CONF_LIMIT,
    CONF_PAGE,
    CONF_START,
    CONF_TRANSPORTATIONS,
    DOMAIN,
    SELECTOR_TRANSPORTATION_TYPES,
)
from homeassistant.components.swiss_public_transport.sensor import (
    SwissPublicTransportSensor,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_DATA_STEP = {
    CONF_DESTINATION: "test_destination",
    CONF_IS_ARRIVAL: False,
    CONF_LIMIT: 3,
    CONF_PAGE: 0,
    CONF_START: "test_start",
    CONF_TRANSPORTATIONS: SELECTOR_TRANSPORTATION_TYPES,
}


async def test_sensor_async_setup_entry(hass: HomeAssistant) -> None:
    """Test successful setup."""

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        return_value=True,
    ):
        sensor = None

        config_entry = MockConfigEntry(
            domain=DOMAIN, entry_id="TEST_ENTRY_ID", data=MOCK_DATA_STEP
        )

        def async_add_entities(
            sensors: list[SwissPublicTransportSensor], update_before_add=None
        ) -> None:
            """Handle callback for add entities."""
            nonlocal sensor
            sensor = sensors[0]

        hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = OpendataTransport(
            start=MOCK_DATA_STEP[CONF_START],
            destination=MOCK_DATA_STEP[CONF_DESTINATION],
            session=async_get_clientsession(hass),
        )

        await async_setup_entry(hass, config_entry, async_add_entities)

        assert sensor is not None
        assert isinstance(sensor, SwissPublicTransportSensor)

        assert sensor.name == "test_start test_destination"
        assert not sensor.availability

        # Set empty response from api
        sensor._opendata.connections = []
        assert sensor.native_value is None
        assert sensor.extra_state_attributes is None

        # Set valid response from api
        sensor._opendata.connections = {
            0: {
                "departure": "2024-01-01T12:00:00+0100",
                "number": 1,
                "platform": "3",
                "transfers": 0,
                "duration": "00:30:00",
                "delay": 3,
            },
            1: {"departure": "2024-01-01T13:00:00+0100"},
            2: {"departure": "2024-01-01T14:00:00+0100"},
        }
        assert sensor.native_value == "2024-01-01T12:00:00+0100"
        assert isinstance(sensor.extra_state_attributes, dict)
        assert (
            sensor.extra_state_attributes[ATTR_DEPARTURE_TIME1]
            == "2024-01-01T13:00:00+0100"
        )
        assert len(sensor.extra_state_attributes[ATTR_DEPARTURE_TIMES]) == 3
        assert sensor.extra_state_attributes[ATTR_DELAY] == 3

        # Limit the responses
        sensor._limit = 1
        assert sensor.extra_state_attributes[ATTR_DEPARTURE_TIME1] is None


async def test_sensor_async_update_entry(hass: HomeAssistant) -> None:
    """Test successful update."""

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        return_value=True,
    ) as mocked_update:
        config_entry = MockConfigEntry(
            domain=DOMAIN, entry_id="TEST_ENTRY_ID", data=MOCK_DATA_STEP
        )

        sensor = None

        def async_add_entities(
            sensors: list[SwissPublicTransportSensor], update_before_add=None
        ) -> None:
            """Handle callback for add entities."""
            nonlocal sensor
            sensor = sensors[0]

        hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = OpendataTransport(
            start=MOCK_DATA_STEP[CONF_START],
            destination=MOCK_DATA_STEP[CONF_DESTINATION],
            session=async_get_clientsession(hass),
        )

        await async_setup_entry(hass, config_entry, async_add_entities)

        assert sensor is not None
        assert isinstance(sensor, SwissPublicTransportSensor)

        await sensor.async_update()
        mocked_update.assert_called_once()
        mocked_update.reset_mock()

        sensor._remaining_time = dt_util.parse_duration("00:01:00")
        await sensor.async_update()
        mocked_update.assert_not_called()
        mocked_update.reset_mock()

        sensor._remaining_time = dt_util.parse_duration("-00:01:00")
        await sensor.async_update()
        mocked_update.assert_called_once()
        mocked_update.reset_mock()

        # Test offset
        sensor._opendata.time = "12:00:00"
        sensor._offset = "00:10:00"
        sensor._remaining_time = dt_util.parse_duration("-00:01:00")
        await sensor.async_update()
        mocked_update.assert_called_once()
        assert (
            sensor._opendata.time
            > (dt_util.now() + dt_util.parse_duration("00:05:00")).time()
        )
