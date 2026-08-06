"""Test the De Lijn config flow."""

from unittest.mock import MagicMock

from pydelijn import (
    DeLijnAuthError,
    DeLijnConnectionError,
    DeLijnError,
    DeLijnNotFoundError,
    DeLijnResponseError,
    Stop,
)
import pytest

from homeassistant.components.delijn.config_flow import CONF_STOP
from homeassistant.components.delijn.const import (
    CONF_NUMBER_OF_DEPARTURES,
    CONF_STOP_ID,
    CONF_STOP_NUMBER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import SelectOptionDict

from .conftest import STOP_NUMBER

from tests.common import MockConfigEntry

API_KEY = "test-api-key"
TITLE = "Brugsepoort (Begijnhoflaan), Gent"


async def test_user_flow_stop_number(
    hass: HomeAssistant, mock_delijn_client: MagicMock
) -> None:
    """Test the full user flow, looking up a stop by its number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {CONF_API_KEY: API_KEY, CONF_STOP_NUMBER: STOP_NUMBER}
    assert result["result"].unique_id == STOP_NUMBER


async def test_user_flow_search(
    hass: HomeAssistant, mock_delijn_client: MagicMock, mock_stop: Stop
) -> None:
    """Test the full user flow, searching for a stop by name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP: "Brugsepoort"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick"
    select_selector = result["data_schema"].schema[CONF_STOP]
    assert select_selector.config["options"] == [
        SelectOptionDict(
            value=STOP_NUMBER,
            label="Brugsepoort (Begijnhoflaan), Gent (200112)",
        )
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {CONF_API_KEY: API_KEY, CONF_STOP_NUMBER: STOP_NUMBER}
    assert result["result"].unique_id == STOP_NUMBER


async def test_stop_title_and_label_without_municipality(
    hass: HomeAssistant, mock_delijn_client: MagicMock
) -> None:
    """Test the title and search label omit the municipality when unknown."""
    stop_without_municipality = Stop(
        entity_number="2", number=STOP_NUMBER, name="Brugsepoort (Begijnhoflaan)"
    )
    mock_delijn_client.search_stops.return_value = [stop_without_municipality]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP: "Brugsepoort"}
    )
    select_selector = result["data_schema"].schema[CONF_STOP]
    assert select_selector.config["options"] == [
        SelectOptionDict(
            value=STOP_NUMBER, label="Brugsepoort (Begijnhoflaan) (200112)"
        )
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Brugsepoort (Begijnhoflaan)"


async def test_search_no_results(
    hass: HomeAssistant, mock_delijn_client: MagicMock
) -> None:
    """Test a search that returns no stops."""
    mock_delijn_client.search_stops.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP: "Nonexistent"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"
    assert result["errors"] == {"base": "no_results"}


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (DeLijnNotFoundError, "invalid_stop"),
        (DeLijnAuthError, "invalid_auth"),
        (DeLijnConnectionError, "cannot_connect"),
        (DeLijnResponseError, "unknown"),
    ],
)
async def test_stop_number_lookup_errors(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    side_effect: type[DeLijnError],
    expected_error: str,
) -> None:
    """Test errors returned while looking up a stop by its number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )

    mock_delijn_client.get_stop.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"
    assert result["errors"] == {"base": expected_error}

    mock_delijn_client.get_stop.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (DeLijnAuthError, "invalid_auth"),
        (DeLijnConnectionError, "cannot_connect"),
        (DeLijnResponseError, "unknown"),
    ],
)
async def test_search_errors(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    side_effect: type[DeLijnError],
    expected_error: str,
) -> None:
    """Test errors returned while searching for a stop by name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )

    mock_delijn_client.search_stops.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP: "Brugsepoort"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"
    assert result["errors"] == {"base": expected_error}

    mock_delijn_client.search_stops.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP: "Brugsepoort"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick"


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when the stop is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test a successful reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"


async def test_reauth_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test reauthentication with an invalid API key, followed by success."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_delijn_client.get_stop.side_effect = DeLijnAuthError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "wrong-api-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    mock_delijn_client.get_stop.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (DeLijnConnectionError, "cannot_connect"),
        (DeLijnResponseError, "unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_delijn_client: MagicMock,
    side_effect: type[DeLijnError],
    expected_error: str,
) -> None:
    """Test reauthentication errors other than invalid auth."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_delijn_client.get_stop.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}


async def test_options_flow(
    hass: HomeAssistant, load_integration: MockConfigEntry
) -> None:
    """Test updating the number-of-departures option."""
    result = await hass.config_entries.options.async_init(load_integration.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_NUMBER_OF_DEPARTURES: 3}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_NUMBER_OF_DEPARTURES: 3}


async def test_import_success(
    hass: HomeAssistant, mock_delijn_client: MagicMock
) -> None:
    """Test importing a stop from the legacy YAML sensor platform."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_API_KEY: API_KEY,
            CONF_STOP_ID: STOP_NUMBER,
            CONF_NUMBER_OF_DEPARTURES: 3,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {CONF_API_KEY: API_KEY, CONF_STOP_NUMBER: STOP_NUMBER}
    assert result["options"] == {CONF_NUMBER_OF_DEPARTURES: 3}
    assert result["result"].unique_id == STOP_NUMBER


async def test_import_already_configured(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test importing a stop that is already configured aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_API_KEY: API_KEY,
            CONF_STOP_ID: STOP_NUMBER,
            CONF_NUMBER_OF_DEPARTURES: 5,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_reason"),
    [
        (DeLijnNotFoundError, "invalid_stop"),
        (DeLijnAuthError, "invalid_auth"),
        (DeLijnConnectionError, "cannot_connect"),
        (DeLijnResponseError, "unknown"),
    ],
)
async def test_import_errors(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    side_effect: type[DeLijnError],
    expected_reason: str,
) -> None:
    """Test import failures are mapped to the correct abort reason."""
    mock_delijn_client.get_stop.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_API_KEY: API_KEY,
            CONF_STOP_ID: STOP_NUMBER,
            CONF_NUMBER_OF_DEPARTURES: 5,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
