"""Tests for Pegel Online config flow."""
from unittest.mock import patch

from aiohttp.client_exceptions import ClientError
from aiopegelonline import Station

from homeassistant.components.pegel_online.const import (
    CONF_STATION,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import PegelOnlineMock

from tests.common import MockConfigEntry

MOCK_USER_DATA_STEP1 = {
    CONF_LOCATION: {CONF_LATITUDE: 51.0, CONF_LONGITUDE: 13.0},
    CONF_RADIUS: 25,
}

MOCK_USER_DATA_STEP2 = {CONF_STATION: "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8"}

MOCK_CONFIG_ENTRY_DATA = {CONF_STATION: "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8"}

MOCK_NEARBY_STATIONS = {
    "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8": Station(
        {
            "uuid": "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8",
            "number": "501060",
            "shortname": "DRESDEN",
            "longname": "DRESDEN",
            "km": 55.63,
            "agency": "STANDORT DRESDEN",
            "longitude": 13.738831783620384,
            "latitude": 51.054459765598125,
            "water": {"shortname": "ELBE", "longname": "ELBE"},
        }
    ),
    "85d686f1-xxxx-xxxx-xxxx-3207b50901a7": Station(
        {
            "uuid": "85d686f1-xxxx-xxxx-xxxx-3207b50901a7",
            "number": "501060",
            "shortname": "MEISSEN",
            "longname": "MEISSEN",
            "km": 82.2,
            "agency": "STANDORT DRESDEN",
            "longitude": 13.475467710324812,
            "latitude": 51.16440557554545,
            "water": {"shortname": "ELBE", "longname": "ELBE"},
        }
    ),
}


async def test_user(hass: HomeAssistant) -> None:
    """Test starting a flow by user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.pegel_online.async_setup_entry", return_value=True
    ) as mock_setup_entry, patch(
        "homeassistant.components.pegel_online.config_flow.PegelOnline",
    ) as pegelonline:
        pegelonline.return_value = PegelOnlineMock(nearby_stations=MOCK_NEARBY_STATIONS)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP1
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "select_station"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP2
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_STATION] == "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8"
        assert result["title"] == "DRESDEN ELBE"

        await hass.async_block_till_done()

    assert mock_setup_entry.called


async def test_user_already_configured(hass: HomeAssistant) -> None:
    """Test starting a flow by user with an already configured statioon."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_ENTRY_DATA,
        unique_id=MOCK_CONFIG_ENTRY_DATA[CONF_STATION],
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.pegel_online.config_flow.PegelOnline",
    ) as pegelonline:
        pegelonline.return_value = PegelOnlineMock(nearby_stations=MOCK_NEARBY_STATIONS)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP1
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "select_station"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP2
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test connection error during user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.pegel_online.async_setup_entry", return_value=True
    ) as mock_setup_entry, patch(
        "homeassistant.components.pegel_online.config_flow.PegelOnline",
    ) as pegelonline:
        # connection issue during setup
        pegelonline.return_value = PegelOnlineMock(side_effect=ClientError)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP1
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "cannot_connect"

        # connection issue solved
        pegelonline.return_value = PegelOnlineMock(nearby_stations=MOCK_NEARBY_STATIONS)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP1
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "select_station"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP2
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_STATION] == "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8"
        assert result["title"] == "DRESDEN ELBE"

        await hass.async_block_till_done()

    assert mock_setup_entry.called


async def test_user_no_stations(hass: HomeAssistant) -> None:
    """Test starting a flow by user which does not find any station."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.pegel_online.async_setup_entry", return_value=True
    ) as mock_setup_entry, patch(
        "homeassistant.components.pegel_online.config_flow.PegelOnline",
    ) as pegelonline:
        # no stations found
        pegelonline.return_value = PegelOnlineMock(nearby_stations={})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP1
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"][CONF_RADIUS] == "no_stations"

        # stations found, go ahead
        pegelonline.return_value = PegelOnlineMock(nearby_stations=MOCK_NEARBY_STATIONS)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP1
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "select_station"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP2
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_STATION] == "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8"
        assert result["title"] == "DRESDEN ELBE"

        await hass.async_block_till_done()

    assert mock_setup_entry.called
