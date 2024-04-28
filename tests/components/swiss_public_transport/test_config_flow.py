"""Test the swiss_public_transport config flow."""

from unittest.mock import patch

from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)
import pytest

from homeassistant.components.swiss_public_transport import config_flow
from homeassistant.components.swiss_public_transport.const import (
    CONF_DESTINATION,
    CONF_START,
    CONF_VIA,
    MAX_VIA,
)
from homeassistant.components.swiss_public_transport.helper import unique_id_from_config
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_DATA_STEP = {
    CONF_START: "test_start",
    CONF_DESTINATION: "test_destination",
}

MOCK_DATA_STEP_ONE_VIA = {
    **MOCK_DATA_STEP,
    CONF_VIA: ["via_station"],
}

MOCK_DATA_STEP_MANY_VIA = {
    **MOCK_DATA_STEP,
    CONF_VIA: ["via_station_1", "via_station_2", "via_station_3"],
}

MOCK_DATA_STEP_TOO_MANY_STATIONS = {
    **MOCK_DATA_STEP,
    CONF_VIA: MOCK_DATA_STEP_ONE_VIA[CONF_VIA] * (MAX_VIA + 1),
}


@pytest.mark.parametrize(
    ("user_input", "config_title"),
    [
        (MOCK_DATA_STEP, "test_start test_destination"),
        (MOCK_DATA_STEP_ONE_VIA, "test_start test_destination via via_station"),
        (
            MOCK_DATA_STEP_MANY_VIA,
            "test_start test_destination via via_station_1, via_station_2, via_station_3",
        ),
    ],
)
async def test_flow_user_init_data_success(
    hass: HomeAssistant, user_input, config_title
) -> None:
    """Test success response."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["handler"] == "swiss_public_transport"
    assert result["data_schema"] == config_flow.DATA_SCHEMA

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["result"].title == config_title

        assert result["data"] == user_input


@pytest.mark.parametrize(
    ("raise_error", "text_error", "user_input_error"),
    [
        (OpendataTransportConnectionError(), "cannot_connect", MOCK_DATA_STEP),
        (OpendataTransportError(), "bad_config", MOCK_DATA_STEP),
        (None, "too_many_via_stations", MOCK_DATA_STEP_TOO_MANY_STATIONS),
        (IndexError(), "unknown", MOCK_DATA_STEP),
    ],
)
async def test_flow_user_init_data_error_and_recover(
    hass: HomeAssistant, raise_error, text_error, user_input_error
) -> None:
    """Test unknown errors."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        side_effect=raise_error,
    ) as mock_OpendataTransport:
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input_error,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == text_error

        # Recover
        mock_OpendataTransport.side_effect = None
        mock_OpendataTransport.return_value = True
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["result"].title == "test_start test_destination"

        assert result["data"] == MOCK_DATA_STEP


async def test_flow_user_init_data_already_configured(hass: HomeAssistant) -> None:
    """Test we abort user data set when entry is already configured."""

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data=MOCK_DATA_STEP,
        unique_id=unique_id_from_config(MOCK_DATA_STEP),
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
