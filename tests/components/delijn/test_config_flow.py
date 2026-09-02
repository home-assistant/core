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

from homeassistant.components.delijn.const import (
    CONF_NUMBER_OF_DEPARTURES,
    CONF_STOP_NUMBER,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import SelectOptionDict

from .conftest import API_KEY, STOP_NUMBER, STOP_TITLE

from tests.common import MockConfigEntry


async def _select_menu_option(
    hass: HomeAssistant, flow_id: str, next_step_id: str
) -> ConfigFlowResult:
    """Choose a menu option on the current step of a subentry flow."""
    return await hass.config_entries.subentries.async_configure(
        flow_id, {"next_step_id": next_step_id}
    )


async def test_user_flow_success(
    hass: HomeAssistant, mock_delijn_client: MagicMock
) -> None:
    """Test the main flow validates the API key and creates the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "De Lijn"
    assert result["data"] == {CONF_API_KEY: API_KEY}
    mock_delijn_client.get_stops_near.assert_awaited_once()


async def test_user_flow_duplicate_key(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the main flow aborts when the API key is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (DeLijnAuthError, "invalid_auth"),
        (DeLijnConnectionError, "cannot_connect"),
        (DeLijnResponseError, "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    side_effect: type[DeLijnError],
    expected_error: str,
) -> None:
    """Test API key validation errors are mapped to the correct error code."""
    mock_delijn_client.get_stops_near.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_delijn_client.get_stops_near.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: API_KEY}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


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


async def test_reauth_reloads_exactly_once(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test a successful reauth reloads the loaded entry exactly once.

    Explicitly reloading on top of the registered update listener would
    reload twice; asserting a single get_passages call (one per the
    entry's single stop coordinator) after reauth proves only the
    listener's reload ran.
    """
    mock_delijn_client.get_passages.reset_mock()

    result = await load_integration.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_delijn_client.get_passages.call_count == 1


async def test_reauth_duplicate_key(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
) -> None:
    """Test reauthenticating aborts if another entry already uses the new key."""
    entry_to_reauth = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "test-api-key"}, title="De Lijn"
    )
    other_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "other-api-key"}, title="De Lijn"
    )
    entry_to_reauth.add_to_hass(hass)
    other_entry.add_to_hass(hass)

    result = await entry_to_reauth.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "other-api-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry_to_reauth.data[CONF_API_KEY] == "test-api-key"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (DeLijnAuthError, "invalid_auth"),
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
    """Test reauthentication errors are mapped to the correct error code."""
    mock_config_entry.add_to_hass(hass)
    mock_delijn_client.get_stops_near.side_effect = side_effect

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}


async def test_main_reconfigure_prefills_current_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test the reconfigure form shows the current API key as a suggestion."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    api_key_key = next(iter(result["data_schema"].schema))
    assert api_key_key.description["suggested_value"] == API_KEY


async def test_main_reconfigure_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test successfully changing the API key on the main entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"


async def test_main_reconfigure_reloads_exactly_once(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test a successful reconfigure reloads the loaded entry exactly once.

    Explicitly reloading on top of the registered update listener would
    reload twice; asserting a single get_passages call (one per the
    entry's single stop coordinator) after reconfigure proves only the
    listener's reload ran.
    """
    mock_delijn_client.get_passages.reset_mock()

    result = await load_integration.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_delijn_client.get_passages.call_count == 1


async def test_main_reconfigure_duplicate_key(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
) -> None:
    """Test reconfiguring aborts if another entry already uses the new key."""
    entry_to_reconfigure = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "test-api-key"}, title="De Lijn"
    )
    other_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "other-api-key"}, title="De Lijn"
    )
    entry_to_reconfigure.add_to_hass(hass)
    other_entry.add_to_hass(hass)

    result = await entry_to_reconfigure.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "other-api-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry_to_reconfigure.data[CONF_API_KEY] == "test-api-key"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (DeLijnAuthError, "invalid_auth"),
        (DeLijnConnectionError, "cannot_connect"),
        (DeLijnResponseError, "unknown"),
    ],
)
async def test_main_reconfigure_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_delijn_client: MagicMock,
    side_effect: type[DeLijnError],
    expected_error: str,
) -> None:
    """Test reconfigure errors are mapped to the correct error code."""
    mock_config_entry.add_to_hass(hass)
    mock_delijn_client.get_stops_near.side_effect = side_effect

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-api-key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": expected_error}
    assert mock_config_entry.data[CONF_API_KEY] == "test-api-key"


async def test_subentry_stop_number(
    hass: HomeAssistant, mock_main_entry: MockConfigEntry, mock_delijn_client: MagicMock
) -> None:
    """Test adding a stop by its number, through the confirm step."""
    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "confirm"
    assert result["menu_options"] == ["create_entry", "user"]
    assert result["description_placeholders"]["departures"] == (
        "4 → Wondelgem (05:07)\n4 → Wondelgem (05:20)"
    )
    assert result["description_placeholders"]["map_url"] == (
        "https://www.openstreetmap.org/?mlat=51.070365&mlon=3.700651"
        "#map=19/51.070365/3.700651"
    )
    assert result["description_placeholders"]["delijn_url"] == (
        "https://www.delijn.be/nl/haltes/200112/"
    )

    result = await _select_menu_option(hass, result["flow_id"], "create_entry")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == STOP_TITLE
    assert result["data"] == {
        CONF_STOP_NUMBER: STOP_NUMBER,
        CONF_NUMBER_OF_DEPARTURES: 5,
    }
    assert result["unique_id"] == STOP_NUMBER


async def test_subentry_confirm_links_without_coordinates(
    hass: HomeAssistant, mock_main_entry: MockConfigEntry, mock_delijn_client: MagicMock
) -> None:
    """Test the map_url placeholder falls back to the delijn.be page."""
    mock_delijn_client.get_stop.return_value = Stop(
        entity_number="2", number=STOP_NUMBER, name="Brugsepoort (Begijnhoflaan)"
    )

    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )

    assert result["description_placeholders"]["delijn_url"] == (
        "https://www.delijn.be/nl/haltes/200112/"
    )
    assert (
        result["description_placeholders"]["map_url"]
        == result["description_placeholders"]["delijn_url"]
    )


async def test_subentry_search(
    hass: HomeAssistant, mock_main_entry: MockConfigEntry, mock_delijn_client: MagicMock
) -> None:
    """Test adding a stop through free-text search and picking a result."""
    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: "Brugsepoort"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick"
    select_selector = result["data_schema"].schema[CONF_STOP]
    assert select_selector.config["options"] == [
        SelectOptionDict(value=STOP_NUMBER, label=STOP_TITLE + " (200112)")
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["create_entry", "pick", "user"]

    result = await _select_menu_option(hass, result["flow_id"], "create_entry")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == STOP_TITLE
    assert result["unique_id"] == STOP_NUMBER


async def test_subentry_stop_title_without_municipality(
    hass: HomeAssistant, mock_main_entry: MockConfigEntry, mock_delijn_client: MagicMock
) -> None:
    """Test the title and search label omit the municipality when unknown."""
    stop_without_municipality = Stop(
        entity_number="2", number=STOP_NUMBER, name="Brugsepoort (Begijnhoflaan)"
    )
    mock_delijn_client.search_stops.return_value = [stop_without_municipality]

    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: "Brugsepoort"}
    )
    select_selector = result["data_schema"].schema[CONF_STOP]
    assert select_selector.config["options"] == [
        SelectOptionDict(
            value=STOP_NUMBER, label="Brugsepoort (Begijnhoflaan) (200112)"
        )
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    result = await _select_menu_option(hass, result["flow_id"], "create_entry")

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Brugsepoort (Begijnhoflaan)"


async def test_subentry_search_no_results(
    hass: HomeAssistant, mock_main_entry: MockConfigEntry, mock_delijn_client: MagicMock
) -> None:
    """Test a search that returns no stops."""
    mock_delijn_client.search_stops.return_value = []

    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: "Nonexistent"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
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
async def test_subentry_stop_number_lookup_errors(
    hass: HomeAssistant,
    mock_main_entry: MockConfigEntry,
    mock_delijn_client: MagicMock,
    side_effect: type[DeLijnError],
    expected_error: str,
) -> None:
    """Test errors returned while looking up a stop by its number."""
    mock_delijn_client.get_stop.side_effect = side_effect

    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    mock_delijn_client.get_stop.side_effect = None
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.MENU


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (DeLijnAuthError, "invalid_auth"),
        (DeLijnConnectionError, "cannot_connect"),
        (DeLijnResponseError, "unknown"),
    ],
)
async def test_subentry_search_errors(
    hass: HomeAssistant,
    mock_main_entry: MockConfigEntry,
    mock_delijn_client: MagicMock,
    side_effect: type[DeLijnError],
    expected_error: str,
) -> None:
    """Test errors returned while searching for a stop by name."""
    mock_delijn_client.search_stops.side_effect = side_effect

    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: "Brugsepoort"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    mock_delijn_client.search_stops.side_effect = None
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: "Brugsepoort"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick"


async def test_subentry_nearby_home_location(
    hass: HomeAssistant, mock_main_entry: MockConfigEntry, mock_delijn_client: MagicMock
) -> None:
    """Test leaving the stop step empty suggests stops near the HA location."""
    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick"
    mock_delijn_client.get_stops_near.assert_awaited_once_with(
        hass.config.latitude, hass.config.longitude, max_results=10
    )
    select_selector = result["data_schema"].schema[CONF_STOP]
    assert select_selector.config["options"] == [
        SelectOptionDict(
            value=STOP_NUMBER,
            label="Brugsepoort (Begijnhoflaan) (200112) – 152 m",
        )
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await _select_menu_option(hass, result["flow_id"], "create_entry")
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_subentry_nearby_chosen_location(
    hass: HomeAssistant, mock_main_entry: MockConfigEntry, mock_delijn_client: MagicMock
) -> None:
    """Test picking a location suggests stops near that location."""
    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LOCATION: {CONF_LATITUDE: 51.05, CONF_LONGITUDE: 3.72}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick"
    mock_delijn_client.get_stops_near.assert_awaited_once_with(
        51.05, 3.72, max_results=10
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await _select_menu_option(hass, result["flow_id"], "create_entry")
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_subentry_nearby_no_results(
    hass: HomeAssistant, mock_main_entry: MockConfigEntry, mock_delijn_client: MagicMock
) -> None:
    """Test no nearby stops being found shows a no_results error."""
    mock_delijn_client.get_stops_near.return_value = []

    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_results"}


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (DeLijnAuthError, "invalid_auth"),
        (DeLijnConnectionError, "cannot_connect"),
        (DeLijnResponseError, "unknown"),
    ],
)
async def test_subentry_nearby_errors(
    hass: HomeAssistant,
    mock_main_entry: MockConfigEntry,
    mock_delijn_client: MagicMock,
    side_effect: type[DeLijnError],
    expected_error: str,
) -> None:
    """Test errors returned while finding nearby stops."""
    mock_delijn_client.get_stops_near.side_effect = side_effect

    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    mock_delijn_client.get_stops_near.side_effect = None
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick"


async def test_subentry_already_configured(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry_with_subentry: MockConfigEntry,
) -> None:
    """Test aborting when the stop is already configured on this entry."""
    mock_config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_with_subentry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await _select_menu_option(hass, result["flow_id"], "create_entry")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_subentry_already_configured_on_another_entry(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry_with_subentry: MockConfigEntry,
) -> None:
    """Test aborting when the stop is already configured on a different entry.

    Sensor unique ids are scoped to the stop number only, so the same stop
    on two entries would collide; the stop must be rejected as a duplicate
    no matter which account already has it.
    """
    mock_config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    other_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "other-api-key"}, title="De Lijn"
    )
    other_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(other_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (other_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await _select_menu_option(hass, result["flow_id"], "create_entry")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_subentry_confirm_search_again(
    hass: HomeAssistant, mock_main_entry: MockConfigEntry, mock_delijn_client: MagicMock
) -> None:
    """Test the confirm step's search-again option returns to the stop step."""
    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.MENU
    assert "pick" not in result["menu_options"]

    result = await _select_menu_option(hass, result["flow_id"], "user")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_subentry_confirm_back_to_pick(
    hass: HomeAssistant, mock_main_entry: MockConfigEntry, mock_delijn_client: MagicMock
) -> None:
    """Test the confirm step's back-to-results option re-renders the dropdown."""
    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: "Brugsepoort"}
    )
    assert result["step_id"] == "pick"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["create_entry", "pick", "user"]

    result = await _select_menu_option(hass, result["flow_id"], "pick")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick"
    select_selector = result["data_schema"].schema[CONF_STOP]
    assert select_selector.config["options"] == [
        SelectOptionDict(value=STOP_NUMBER, label=STOP_TITLE + " (200112)")
    ]


async def test_subentry_stale_search_results_cleared(
    hass: HomeAssistant, mock_main_entry: MockConfigEntry, mock_delijn_client: MagicMock
) -> None:
    """Test a direct number entry after a search clears the prior results."""
    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: "Brugsepoort"}
    )
    assert result["step_id"] == "pick"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert "pick" in result["menu_options"]

    result = await _select_menu_option(hass, result["flow_id"], "user")
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["create_entry", "user"]


async def test_subentry_confirm_no_upcoming_departures(
    hass: HomeAssistant, mock_main_entry: MockConfigEntry, mock_delijn_client: MagicMock
) -> None:
    """Test the confirm step still allows confirming with no upcoming departures."""
    mock_delijn_client.get_passages.return_value = []

    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["description_placeholders"]["departures"] == ""

    result = await _select_menu_option(hass, result["flow_id"], "create_entry")
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_subentry_confirm_departures_error(
    hass: HomeAssistant, mock_main_entry: MockConfigEntry, mock_delijn_client: MagicMock
) -> None:
    """Test the confirm step still allows confirming if the preview fails."""
    mock_delijn_client.get_passages.side_effect = DeLijnConnectionError

    result = await hass.config_entries.subentries.async_init(
        (mock_main_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STOP: STOP_NUMBER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["description_placeholders"]["departures"] == ""

    result = await _select_menu_option(hass, result["flow_id"], "create_entry")
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_subentry_reconfigure(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    mock_delijn_client: MagicMock,
) -> None:
    """Test changing the number of departures for an existing stop."""
    subentry_id = next(iter(load_integration.subentries))

    result = await hass.config_entries.subentries.async_init(
        (load_integration.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["description_placeholders"] == {"stop_number": STOP_NUMBER}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NUMBER_OF_DEPARTURES: 3}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert load_integration.subentries[subentry_id].data[CONF_NUMBER_OF_DEPARTURES] == 3
