"""Tests for the Entur public transport config flow."""

from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
import pytest

from homeassistant.components.entur_public_transport.const import (
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_STOP_IDS,
    CONF_WHITELIST_LINES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_entur_client: MagicMock,
) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STOP_IDS: ["NSR:StopPlace:548"],
            CONF_SHOW_ON_MAP: False,
            CONF_WHITELIST_LINES: [],
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Entur NSR:StopPlace:548"
    assert result["data"] == {
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
    }
    assert result["options"] == {
        CONF_SHOW_ON_MAP: False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_with_quay(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_entur_client: MagicMock,
) -> None:
    """Test user flow with a quay ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STOP_IDS: ["NSR:Quay:48550"],
            CONF_SHOW_ON_MAP: False,
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Entur NSR:Quay:48550"


async def test_user_flow_invalid_stop_id(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_entur_client: MagicMock,
) -> None:
    """Test user flow with invalid stop ID and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STOP_IDS: ["invalid_id"],
            CONF_SHOW_ON_MAP: False,
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_stop_id"}

    # Recover with valid input
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STOP_IDS: ["NSR:StopPlace:548"],
            CONF_SHOW_ON_MAP: False,
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "side_effect",
    [ClientError("Connection error"), TimeoutError("Timeout")],
)
async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_entur_client: MagicMock,
    side_effect: Exception,
) -> None:
    """Test user flow when API connection fails and recovery."""
    mock_entur_client.update = AsyncMock(side_effect=side_effect)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STOP_IDS: ["NSR:StopPlace:548"],
            CONF_SHOW_ON_MAP: False,
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover after connection is restored
    mock_entur_client.update = AsyncMock()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STOP_IDS: ["NSR:StopPlace:548"],
            CONF_SHOW_ON_MAP: False,
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_entur_client: MagicMock,
) -> None:
    """Test user flow when an unexpected error occurs and recovery."""
    mock_entur_client.update = AsyncMock(side_effect=Exception("Unexpected error"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STOP_IDS: ["NSR:StopPlace:548"],
            CONF_SHOW_ON_MAP: False,
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover after error resolves
    mock_entur_client.update = AsyncMock()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STOP_IDS: ["NSR:StopPlace:548"],
            CONF_SHOW_ON_MAP: False,
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
) -> None:
    """Test user flow when entry already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STOP_IDS: ["NSR:StopPlace:548"],
            CONF_SHOW_ON_MAP: False,
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SHOW_ON_MAP: True,
            CONF_WHITELIST_LINES: ["NSB:Line:45"],
            CONF_OMIT_NON_BOARDING: False,
            CONF_NUMBER_OF_DEPARTURES: 5,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SHOW_ON_MAP: True,
        CONF_WHITELIST_LINES: ["NSB:Line:45"],
        CONF_OMIT_NON_BOARDING: False,
        CONF_NUMBER_OF_DEPARTURES: 5,
    }


async def test_import_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_entur_client: MagicMock,
) -> None:
    """Test successful import from YAML configuration."""
    yaml_config = {
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
        CONF_NAME: "My Bus Stop",
        "show_on_map": False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=yaml_config,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Bus Stop"
    assert result["data"] == {
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
    }
    assert result["options"] == {
        CONF_SHOW_ON_MAP: False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }


async def test_import_flow_invalid_stop_id(hass: HomeAssistant) -> None:
    """Test import flow with invalid stop ID."""
    yaml_config = {
        CONF_STOP_IDS: ["invalid_id"],
        CONF_NAME: "My Bus Stop",
        "show_on_map": False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=yaml_config,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_stop_id"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (ClientError("Connection error"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_import_flow_error(
    hass: HomeAssistant,
    mock_entur_client: MagicMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test import flow aborts on API errors."""
    mock_entur_client.update = AsyncMock(side_effect=side_effect)

    yaml_config = {
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
        CONF_NAME: "My Bus Stop",
        "show_on_map": False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=yaml_config,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
) -> None:
    """Test import flow when entry already exists."""
    mock_config_entry.add_to_hass(hass)

    yaml_config = {
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
        CONF_NAME: "My Bus Stop",
        "show_on_map": False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=yaml_config,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
