"""Test the swiss_public_transport config flow."""
from unittest.mock import AsyncMock, patch

from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.swiss_public_transport import config_flow
from homeassistant.components.swiss_public_transport.const import (
    CONF_ACCESSIBILITY,
    CONF_BIKE,
    CONF_COUCHETTE,
    CONF_DATE,
    CONF_DESTINATION,
    CONF_DIRECT,
    CONF_IS_ARRIVAL,
    CONF_LIMIT,
    CONF_OFFSET,
    CONF_PAGE,
    CONF_SLEEPER,
    CONF_START,
    CONF_TIME,
    CONF_TRANSPORTATIONS,
    CONF_VIA,
    SELECTOR_TRANSPORTATION_TYPES,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

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


@pytest.mark.parametrize(
    ("optional_config", "entry_name"),
    [
        ({}, "test_start test_destination"),
        (
            {CONF_DIRECT: True},
            "test_start test_destination direct",
        ),
        (
            {CONF_VIA: ["test_via_station"]},
            "test_start test_destination via test_via_station",
        ),
        (
            {CONF_DATE: "2024-01-01", CONF_TIME: "12:00:00"},
            "test_start test_destination on 2024-01-01 at 12:00:00",
        ),
        (
            {CONF_OFFSET: {"hours": 0, "minutes": 10, "seconds": 0}},
            "test_start test_destination in 00:10:00",
        ),
        (
            {CONF_LIMIT: 2, CONF_PAGE: 1},
            "test_start test_destination limited to 2 on page 1",
        ),
        (
            {CONF_TRANSPORTATIONS: ["train"]},
            "test_start test_destination using train",
        ),
        (
            {CONF_ACCESSIBILITY: ["independent_boarding"]},
            "test_start test_destination providing independent_boarding",
        ),
        (
            {CONF_BIKE: True, CONF_SLEEPER: True, CONF_COUCHETTE: True},
            "test_start test_destination with bike with couchette with sleeper",
        ),
    ],
)
async def test_flow_user_init_data_success(
    hass: HomeAssistant, optional_config, entry_name
) -> None:
    """Test success response."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
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
            user_input={**MOCK_DATA_STEP, **optional_config},
        )

        assert result["type"] == "create_entry"
        assert result["result"].title == entry_name

        assert result["data"] == {**MOCK_DATA_STEP, **optional_config}


@pytest.mark.parametrize(
    ("faulty_config", "text_error"),
    [
        ({CONF_LIMIT: 1.2}, "limit_not_an_integer"),
        ({CONF_PAGE: 1.2}, "page_not_an_integer"),
        ({CONF_VIA: ["a", "b", "c", "d", "e", "f"]}, "too_many_via_stations"),
    ],
)
async def test_flow_user_init_data_config_error(
    hass: HomeAssistant, faulty_config, text_error
) -> None:
    """Test config errors."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**MOCK_DATA_STEP, **faulty_config},
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == text_error


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (OpendataTransportConnectionError(), "cannot_connect"),
        (OpendataTransportError(), "bad_config"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_user_init_data_lib_error(
    hass: HomeAssistant, raise_error, text_error
) -> None:
    """Test lib errors."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        side_effect=raise_error,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] == "form"
        assert result["errors"]["base"] == text_error


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (OpendataTransportConnectionError(), "cannot_connect"),
        (OpendataTransportError(), "bad_config"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_user_init_data_unknown_error_and_recover(
    hass: HomeAssistant, raise_error, text_error
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
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] == "form"
        assert result["errors"]["base"] == text_error

        # Recover
        mock_OpendataTransport.side_effect = None
        mock_OpendataTransport.return_value = True
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] == "create_entry"
        assert result["result"].title == "test_start test_destination"

        assert result["data"] == MOCK_DATA_STEP


async def test_flow_user_init_data_already_configured(hass: HomeAssistant) -> None:
    """Test we abort user data set when entry is already configured."""

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data=MOCK_DATA_STEP,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_STEP,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


MOCK_DATA_IMPORT = {
    CONF_NAME: "test_name",
    CONF_DESTINATION: "test_destination",
    CONF_IS_ARRIVAL: False,
    CONF_LIMIT: 3,
    CONF_PAGE: 0,
    CONF_START: "test_start",
    CONF_TRANSPORTATIONS: SELECTOR_TRANSPORTATION_TYPES,
}


@pytest.mark.parametrize(
    ("optional_config", "entry_name"),
    [
        ({}, "test_start test_destination"),
        (
            {CONF_DIRECT: True},
            "test_start test_destination direct",
        ),
        (
            {CONF_VIA: ["test_via_station"]},
            "test_start test_destination via test_via_station",
        ),
        (
            {CONF_DATE: "2024-01-01", CONF_TIME: "12:00:00"},
            "test_start test_destination on 2024-01-01 at 12:00:00",
        ),
        (
            {CONF_OFFSET: {"hours": 0, "minutes": 10, "seconds": 0}},
            "test_start test_destination in 00:10:00",
        ),
        (
            {CONF_LIMIT: 2, CONF_PAGE: 1},
            "test_start test_destination limited to 2 on page 1",
        ),
        (
            {CONF_TRANSPORTATIONS: ["train"]},
            "test_start test_destination using train",
        ),
        (
            {CONF_ACCESSIBILITY: ["independent_boarding"]},
            "test_start test_destination providing independent_boarding",
        ),
        (
            {CONF_BIKE: True, CONF_SLEEPER: True, CONF_COUCHETTE: True},
            "test_start test_destination with bike with couchette with sleeper",
        ),
    ],
)
async def test_import(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    optional_config,
    entry_name,
) -> None:
    """Test import flow."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={**MOCK_DATA_IMPORT, **optional_config},
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == {**MOCK_DATA_IMPORT, **optional_config}
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("faulty_config", "text_error"),
    [
        ({CONF_LIMIT: 1.2}, "limit_not_an_integer"),
        ({CONF_PAGE: 1.2}, "page_not_an_integer"),
        ({CONF_VIA: ["a", "b", "c", "d", "e", "f"]}, "too_many_via_stations"),
    ],
)
async def test_import_config_error(
    hass: HomeAssistant, faulty_config, text_error
) -> None:
    """Test import flow config error."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={**MOCK_DATA_IMPORT, **faulty_config},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == text_error


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (OpendataTransportConnectionError(), "cannot_connect"),
        (OpendataTransportError(), "bad_config"),
        (IndexError(), "unknown"),
    ],
)
async def test_import_lib_error(hass: HomeAssistant, raise_error, text_error) -> None:
    """Test import flow lib error."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport.async_get_data",
        autospec=True,
        side_effect=raise_error,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_DATA_IMPORT,
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == text_error


async def test_import_already_configured(hass: HomeAssistant) -> None:
    """Test we abort import when entry is already configured."""

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data=MOCK_DATA_IMPORT,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_DATA_IMPORT,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
