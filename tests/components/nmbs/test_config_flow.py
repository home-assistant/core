"""Test the NMBS config flow."""

from typing import Any
from unittest.mock import AsyncMock

from mashumaro.exceptions import MissingField
from pyrail import ApiUnavailableError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.nmbs.const import (
    CONF_EXCLUDE_VIAS,
    CONF_STATION_FROM,
    CONF_STATION_TO,
    CONNECTION_UNIQUE_ID_PREFIX,
    DOMAIN,
    LIVEBOARD_UNIQUE_ID_PREFIX,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .conftest import STATION_FROM, STATION_TO

DUMMY_DATA: dict[str, Any] = {
    "STAT_BRUSSELS_NORTH": "BE.NMBS.008812005",
    "STAT_BRUSSELS_CENTRAL": "BE.NMBS.008813003",
    "STAT_BRUSSELS_SOUTH": "BE.NMBS.008814001",
}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_nmbs_client: AsyncMock) -> None:
    """Test the full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
            CONF_SHOW_ON_MAP: True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["title"]
        == "Train from Brussel-Noord/Bruxelles-Nord to Brussel-Zuid/Bruxelles-Midi"
    )
    assert result["data"] == {
        CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
        CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
    }
    assert result["result"].options == {CONF_SHOW_ON_MAP: True}
    assert (
        result["result"].unique_id
        == f"{DUMMY_DATA['STAT_BRUSSELS_NORTH']}_{DUMMY_DATA['STAT_BRUSSELS_SOUTH']}"
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_same_station(hass: HomeAssistant, mock_nmbs_client: AsyncMock) -> None:
    """Test selecting the same station."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "same_station"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_abort_if_exists(
    hass: HomeAssistant, mock_nmbs_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test aborting the flow if the entry already exists."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dont_abort_if_exists_when_vias_differs(
    hass: HomeAssistant, mock_nmbs_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test creating an entry when the exclude-vias option differs."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
            CONF_EXCLUDE_VIAS: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"{mock_config_entry.unique_id}_excl_vias"


@pytest.mark.parametrize(
    "stations_side_effect",
    [
        pytest.param([None], id="no_response"),
        pytest.param(ApiUnavailableError("API unavailable"), id="api_unavailable"),
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(ValueError("Unexpected response schema"), id="decoding_error"),
        pytest.param(MissingField("name", "str", "StationDetails"), id="missing_field"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_unavailable_api_errors(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    stations_side_effect: list[None] | Exception | type[Exception],
) -> None:
    """Test the flow aborts when the station list cannot be fetched and recovers."""
    mock_nmbs_client.get_stations.side_effect = stations_side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "api_unavailable"

    mock_nmbs_client.get_stations.side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATION_FROM: DUMMY_DATA["STAT_BRUSSELS_NORTH"],
            CONF_STATION_TO: DUMMY_DATA["STAT_BRUSSELS_SOUTH"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"{STATION_FROM}_{STATION_TO}"


async def test_reconfigure(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow only changes Direct connections only and works offline."""
    mock_config_entry.add_to_hass(hass)
    mock_nmbs_client.get_stations.side_effect = ApiUnavailableError("API unavailable")

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert {str(key) for key in result["data_schema"].schema} == {CONF_EXCLUDE_VIAS}

    mock_nmbs_client.get_stations.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EXCLUDE_VIAS: True},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.unique_id == f"{STATION_FROM}_{STATION_TO}_excl_vias"
    assert mock_config_entry.data == {
        CONF_STATION_FROM: STATION_FROM,
        CONF_STATION_TO: STATION_TO,
        CONF_EXCLUDE_VIAS: True,
    }


async def test_reconfigure_migrates_entities(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test reconfiguration keeps entity IDs and the stored custom name."""
    entry = MockConfigEntry(
        domain=mock_config_entry.domain,
        title=mock_config_entry.title,
        data={**mock_config_entry.data, CONF_NAME: "My train to work"},
        unique_id=mock_config_entry.unique_id,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    connection_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{CONNECTION_UNIQUE_ID_PREFIX}{entry.unique_id}"
    )
    old_entry_unique_id = entry.unique_id
    liveboard_from_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{LIVEBOARD_UNIQUE_ID_PREFIX}{STATION_FROM}_{entry.unique_id}",
    )
    liveboard_to_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{LIVEBOARD_UNIQUE_ID_PREFIX}{STATION_TO}_{entry.unique_id}"
    )
    assert connection_id is not None
    assert liveboard_from_id is not None
    assert liveboard_to_id is not None
    entity_registry.async_update_entity(liveboard_from_id, disabled_by=None)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EXCLUDE_VIAS: True},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == f"{STATION_FROM}_{STATION_TO}_excl_vias"
    assert entry.data[CONF_NAME] == "My train to work"

    new_entry_unique_id = f"{STATION_FROM}_{STATION_TO}_excl_vias"
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{CONNECTION_UNIQUE_ID_PREFIX}{new_entry_unique_id}"
        )
        == connection_id
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            f"{LIVEBOARD_UNIQUE_ID_PREFIX}{STATION_FROM}_{new_entry_unique_id}",
        )
        == liveboard_from_id
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            f"{LIVEBOARD_UNIQUE_ID_PREFIX}{STATION_TO}_{new_entry_unique_id}",
        )
        == liveboard_to_id
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{CONNECTION_UNIQUE_ID_PREFIX}{old_entry_unique_id}"
        )
        is None
    )

    liveboard_entry = entity_registry.async_get(liveboard_from_id)
    assert liveboard_entry is not None
    assert liveboard_entry.disabled_by is None
    await hass.async_block_till_done()

    connection_state = hass.states.get(connection_id)
    assert connection_state is not None
    assert connection_state.state == "10"
    liveboard_state = hass.states.get(liveboard_from_id)
    assert liveboard_state is not None
    assert liveboard_state.state == "Track 3 - Blankenberge"


async def test_reconfigure_abort_when_route_configured(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test reconfiguration aborts when another entry has the same options."""
    entry = mock_config_entry
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    other = MockConfigEntry(
        domain=DOMAIN,
        title=entry.title,
        data={**entry.data, CONF_EXCLUDE_VIAS: True},
        unique_id=f"{STATION_FROM}_{STATION_TO}_excl_vias",
    )
    other.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EXCLUDE_VIAS: True},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == f"{STATION_FROM}_{STATION_TO}"
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{CONNECTION_UNIQUE_ID_PREFIX}{entry.unique_id}"
        )
        is not None
    )


async def test_reconfigure_skips_taken_unique_id(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration leaves an entity alone when its new unique ID is taken."""
    entry = mock_config_entry
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    old_liveboard_unique_id = (
        f"{LIVEBOARD_UNIQUE_ID_PREFIX}{STATION_FROM}_{entry.unique_id}"
    )
    new_liveboard_unique_id = f"{LIVEBOARD_UNIQUE_ID_PREFIX}{STATION_FROM}_{STATION_FROM}_{STATION_TO}_excl_vias"
    liveboard_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, old_liveboard_unique_id
    )
    assert liveboard_id is not None
    taken = entity_registry.async_get_or_create(
        "sensor", DOMAIN, new_liveboard_unique_id, config_entry=entry
    )

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EXCLUDE_VIAS: True},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, old_liveboard_unique_id)
        == liveboard_id
    )
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, new_liveboard_unique_id)
        == taken.entity_id
    )


async def test_options_flow(
    hass: HomeAssistant,
    mock_nmbs_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the options flow turns the map location on and reloads the entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SHOW_ON_MAP: True}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_SHOW_ON_MAP: True}
    connection_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{CONNECTION_UNIQUE_ID_PREFIX}{mock_config_entry.unique_id}"
    )
    assert connection_id is not None
    state = hass.states.get(connection_id)
    assert state is not None
    assert "latitude" in state.attributes
