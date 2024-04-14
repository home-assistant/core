"""Tests for Pegel Online config flow."""

from unittest.mock import patch

from aiohttp.client_exceptions import ClientError

from homeassistant.components.pegel_online.const import CONF_STATION, DOMAIN
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
from .const import MOCK_CONFIG_ENTRY_DATA_DRESDEN, MOCK_NEARBY_STATIONS

from tests.common import MockConfigEntry

MOCK_USER_DATA_STEP1 = {
    CONF_LOCATION: {CONF_LATITUDE: 51.0, CONF_LONGITUDE: 13.0},
    CONF_RADIUS: 25,
}

MOCK_USER_DATA_STEP2 = {CONF_STATION: "70272185-xxxx-xxxx-xxxx-43bea330dcae"}


async def test_user(hass: HomeAssistant) -> None:
    """Test starting a flow by user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.pegel_online.async_setup_entry", return_value=True
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.pegel_online.config_flow.PegelOnline",
        ) as pegelonline,
    ):
        pegelonline.return_value = PegelOnlineMock(nearby_stations=MOCK_NEARBY_STATIONS)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP1
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_station"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP2
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_STATION] == "70272185-xxxx-xxxx-xxxx-43bea330dcae"
        assert result["title"] == "DRESDEN ELBE"

        await hass.async_block_till_done()

    assert mock_setup_entry.called


async def test_user_already_configured(hass: HomeAssistant) -> None:
    """Test starting a flow by user with an already configured statioon."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_ENTRY_DATA_DRESDEN,
        unique_id=MOCK_CONFIG_ENTRY_DATA_DRESDEN[CONF_STATION],
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.pegel_online.config_flow.PegelOnline",
    ) as pegelonline:
        pegelonline.return_value = PegelOnlineMock(nearby_stations=MOCK_NEARBY_STATIONS)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP1
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_station"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP2
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test connection error during user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.pegel_online.async_setup_entry", return_value=True
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.pegel_online.config_flow.PegelOnline",
        ) as pegelonline,
    ):
        # connection issue during setup
        pegelonline.return_value = PegelOnlineMock(side_effect=ClientError)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP1
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "cannot_connect"

        # connection issue solved
        pegelonline.return_value = PegelOnlineMock(nearby_stations=MOCK_NEARBY_STATIONS)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP1
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_station"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP2
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_STATION] == "70272185-xxxx-xxxx-xxxx-43bea330dcae"
        assert result["title"] == "DRESDEN ELBE"

        await hass.async_block_till_done()

    assert mock_setup_entry.called


async def test_user_no_stations(hass: HomeAssistant) -> None:
    """Test starting a flow by user which does not find any station."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.pegel_online.async_setup_entry", return_value=True
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.pegel_online.config_flow.PegelOnline",
        ) as pegelonline,
    ):
        # no stations found
        pegelonline.return_value = PegelOnlineMock(nearby_stations={})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP1
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"][CONF_RADIUS] == "no_stations"

        # stations found, go ahead
        pegelonline.return_value = PegelOnlineMock(nearby_stations=MOCK_NEARBY_STATIONS)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP1
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_station"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA_STEP2
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_STATION] == "70272185-xxxx-xxxx-xxxx-43bea330dcae"
        assert result["title"] == "DRESDEN ELBE"

        await hass.async_block_till_done()

    assert mock_setup_entry.called
