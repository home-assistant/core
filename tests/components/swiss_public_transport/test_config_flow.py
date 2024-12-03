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
    CONF_TIME_FIXED,
    CONF_TIME_MODE,
    CONF_TIME_OFFSET,
    CONF_TIME_STATION,
    CONF_VIA,
    MAX_VIA,
)
from homeassistant.components.swiss_public_transport.helper import unique_id_from_config
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_USER_DATA_STEP = {
    CONF_START: "test_start",
    CONF_DESTINATION: "test_destination",
    CONF_TIME_STATION: "departure",
    CONF_TIME_MODE: "now",
}

MOCK_USER_DATA_STEP_ONE_VIA = {
    **MOCK_USER_DATA_STEP,
    CONF_VIA: ["via_station"],
}

MOCK_USER_DATA_STEP_MANY_VIA = {
    **MOCK_USER_DATA_STEP,
    CONF_VIA: ["via_station_1", "via_station_2", "via_station_3"],
}

MOCK_USER_DATA_STEP_TOO_MANY_STATIONS = {
    **MOCK_USER_DATA_STEP,
    CONF_VIA: MOCK_USER_DATA_STEP_ONE_VIA[CONF_VIA] * (MAX_VIA + 1),
}

MOCK_USER_DATA_STEP_ARRIVAL = {
    **MOCK_USER_DATA_STEP,
    CONF_TIME_STATION: "arrival",
}

MOCK_USER_DATA_STEP_TIME_FIXED = {
    **MOCK_USER_DATA_STEP,
    CONF_TIME_MODE: "fixed",
}

MOCK_USER_DATA_STEP_TIME_FIXED_OFFSET = {
    **MOCK_USER_DATA_STEP,
    CONF_TIME_MODE: "offset",
}

MOCK_USER_DATA_STEP_BAD = {
    **MOCK_USER_DATA_STEP,
    CONF_TIME_MODE: "bad",
}

MOCK_ADVANCED_DATA_STEP_TIME = {
    CONF_TIME_FIXED: "18:03:00",
}

MOCK_ADVANCED_DATA_STEP_TIME_OFFSET = {
    CONF_TIME_OFFSET: {"hours": 0, "minutes": 10, "seconds": 0},
}


@pytest.mark.parametrize(
    ("user_input", "time_mode_input", "config_title"),
    [
        (MOCK_USER_DATA_STEP, None, "test_start test_destination"),
        (
            MOCK_USER_DATA_STEP_ONE_VIA,
            None,
            "test_start test_destination via via_station",
        ),
        (
            MOCK_USER_DATA_STEP_MANY_VIA,
            None,
            "test_start test_destination via via_station_1, via_station_2, via_station_3",
        ),
        (MOCK_USER_DATA_STEP_ARRIVAL, None, "test_start test_destination arrival"),
        (
            MOCK_USER_DATA_STEP_TIME_FIXED,
            MOCK_ADVANCED_DATA_STEP_TIME,
            "test_start test_destination at 18:03:00",
        ),
        (
            MOCK_USER_DATA_STEP_TIME_FIXED_OFFSET,
            MOCK_ADVANCED_DATA_STEP_TIME_OFFSET,
            "test_start test_destination in 00:10:00",
        ),
    ],
)
async def test_flow_user_init_data_success(
    hass: HomeAssistant, user_input, time_mode_input, config_title
) -> None:
    """Test success response."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["handler"] == "swiss_public_transport"
    assert result["data_schema"] == config_flow.USER_DATA_SCHEMA

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        if time_mode_input:
            assert result["type"] == FlowResultType.FORM
            if CONF_TIME_FIXED in time_mode_input:
                assert result["step_id"] == "time_fixed"
            if CONF_TIME_OFFSET in time_mode_input:
                assert result["step_id"] == "time_offset"
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=time_mode_input,
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["result"].title == config_title

        assert result["data"] == {**user_input, **(time_mode_input or {})}


@pytest.mark.parametrize(
    ("raise_error", "text_error", "user_input_error"),
    [
        (OpendataTransportConnectionError(), "cannot_connect", MOCK_USER_DATA_STEP),
        (OpendataTransportError(), "bad_config", MOCK_USER_DATA_STEP),
        (None, "too_many_via_stations", MOCK_USER_DATA_STEP_TOO_MANY_STATIONS),
        (IndexError(), "unknown", MOCK_USER_DATA_STEP),
    ],
)
async def test_flow_user_init_data_error_and_recover_on_step_1(
    hass: HomeAssistant, raise_error, text_error, user_input_error
) -> None:
    """Test errors in user step."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        side_effect=raise_error,
    ) as mock_OpendataTransport:
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
            user_input=MOCK_USER_DATA_STEP,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["result"].title == "test_start test_destination"

        assert result["data"] == MOCK_USER_DATA_STEP


@pytest.mark.parametrize(
    ("raise_error", "text_error", "user_input"),
    [
        (
            OpendataTransportConnectionError(),
            "cannot_connect",
            MOCK_ADVANCED_DATA_STEP_TIME,
        ),
        (OpendataTransportError(), "bad_config", MOCK_ADVANCED_DATA_STEP_TIME),
        (IndexError(), "unknown", MOCK_ADVANCED_DATA_STEP_TIME),
    ],
)
async def test_flow_user_init_data_error_and_recover_on_step_2(
    hass: HomeAssistant, raise_error, text_error, user_input
) -> None:
    """Test errors in time mode step."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["handler"] == "swiss_public_transport"
    assert result["data_schema"] == config_flow.USER_DATA_SCHEMA

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_USER_DATA_STEP_TIME_FIXED,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "time_fixed"

    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        side_effect=raise_error,
    ) as mock_OpendataTransport:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == text_error

        # Recover
        mock_OpendataTransport.side_effect = None
        mock_OpendataTransport.return_value = True
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["result"].title == "test_start test_destination at 18:03:00"


async def test_flow_user_init_data_already_configured(hass: HomeAssistant) -> None:
    """Test we abort user data set when entry is already configured."""

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data=MOCK_USER_DATA_STEP,
        unique_id=unique_id_from_config(MOCK_USER_DATA_STEP),
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
            user_input=MOCK_USER_DATA_STEP,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
