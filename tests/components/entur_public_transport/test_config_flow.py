"""Tests for the Entur public transport config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError

from homeassistant.components.entur_public_transport.const import (
    CONF_EXPAND_PLATFORMS,
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


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.entur_public_transport.config_flow.EnturPublicTransportData"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client.update = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_STOP_IDS: ["NSR:StopPlace:548"],
                CONF_EXPAND_PLATFORMS: True,
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
        CONF_EXPAND_PLATFORMS: True,
        CONF_SHOW_ON_MAP: False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }


async def test_user_flow_with_quay(hass: HomeAssistant) -> None:
    """Test user flow with a quay ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.entur_public_transport.config_flow.EnturPublicTransportData"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client.update = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_STOP_IDS: ["NSR:Quay:48550"],
                CONF_EXPAND_PLATFORMS: True,
                CONF_SHOW_ON_MAP: False,
                CONF_OMIT_NON_BOARDING: True,
                CONF_NUMBER_OF_DEPARTURES: 2,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Entur NSR:Quay:48550"


async def test_user_flow_invalid_stop_id(hass: HomeAssistant) -> None:
    """Test user flow with invalid stop ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STOP_IDS: ["invalid_id"],
            CONF_EXPAND_PLATFORMS: True,
            CONF_SHOW_ON_MAP: False,
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_stop_id"}


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user flow when API connection fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.entur_public_transport.config_flow.EnturPublicTransportData"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client.update = AsyncMock(side_effect=ClientError("Connection error"))
        mock_client_class.return_value = mock_client

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_STOP_IDS: ["NSR:StopPlace:548"],
                CONF_EXPAND_PLATFORMS: True,
                CONF_SHOW_ON_MAP: False,
                CONF_OMIT_NON_BOARDING: True,
                CONF_NUMBER_OF_DEPARTURES: 2,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_timeout(hass: HomeAssistant) -> None:
    """Test user flow when API times out."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.entur_public_transport.config_flow.EnturPublicTransportData"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client.update = AsyncMock(side_effect=TimeoutError("Timeout"))
        mock_client_class.return_value = mock_client

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_STOP_IDS: ["NSR:StopPlace:548"],
                CONF_EXPAND_PLATFORMS: True,
                CONF_SHOW_ON_MAP: False,
                CONF_OMIT_NON_BOARDING: True,
                CONF_NUMBER_OF_DEPARTURES: 2,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test user flow when an unexpected error occurs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.entur_public_transport.config_flow.EnturPublicTransportData"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client.update = AsyncMock(side_effect=Exception("Unexpected error"))
        mock_client_class.return_value = mock_client

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_STOP_IDS: ["NSR:StopPlace:548"],
                CONF_EXPAND_PLATFORMS: True,
                CONF_SHOW_ON_MAP: False,
                CONF_OMIT_NON_BOARDING: True,
                CONF_NUMBER_OF_DEPARTURES: 2,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test user flow when entry already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Entur NSR:StopPlace:548",
        data={
            CONF_STOP_IDS: ["NSR:StopPlace:548"],
        },
        unique_id="NSR:StopPlace:548",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.entur_public_transport.config_flow.EnturPublicTransportData"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client.update = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_STOP_IDS: ["NSR:StopPlace:548"],
                CONF_EXPAND_PLATFORMS: True,
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
            CONF_EXPAND_PLATFORMS: False,
            CONF_SHOW_ON_MAP: True,
            CONF_WHITELIST_LINES: ["NSB:Line:45"],
            CONF_OMIT_NON_BOARDING: False,
            CONF_NUMBER_OF_DEPARTURES: 5,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_EXPAND_PLATFORMS: False,
        CONF_SHOW_ON_MAP: True,
        CONF_WHITELIST_LINES: ["NSB:Line:45"],
        CONF_OMIT_NON_BOARDING: False,
        CONF_NUMBER_OF_DEPARTURES: 5,
    }


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test successful import from YAML configuration."""
    yaml_config = {
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
        CONF_EXPAND_PLATFORMS: True,
        CONF_NAME: "My Bus Stop",
        "show_on_map": False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }

    with patch(
        "homeassistant.components.entur_public_transport.config_flow.EnturPublicTransportData"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client.update = AsyncMock()
        mock_client_class.return_value = mock_client

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
        CONF_EXPAND_PLATFORMS: True,
        CONF_SHOW_ON_MAP: False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }


async def test_import_flow_invalid_stop_id(hass: HomeAssistant) -> None:
    """Test import flow with invalid stop ID."""
    yaml_config = {
        CONF_STOP_IDS: ["invalid_id"],
        CONF_EXPAND_PLATFORMS: True,
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


async def test_import_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test import flow when API connection fails."""
    yaml_config = {
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
        CONF_EXPAND_PLATFORMS: True,
        CONF_NAME: "My Bus Stop",
        "show_on_map": False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }

    with patch(
        "homeassistant.components.entur_public_transport.config_flow.EnturPublicTransportData"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client.update = AsyncMock(side_effect=ClientError("Connection error"))
        mock_client_class.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=yaml_config,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test import flow when an unexpected error occurs."""
    yaml_config = {
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
        CONF_EXPAND_PLATFORMS: True,
        CONF_NAME: "My Bus Stop",
        "show_on_map": False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }

    with patch(
        "homeassistant.components.entur_public_transport.config_flow.EnturPublicTransportData"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client.update = AsyncMock(side_effect=Exception("Unexpected error"))
        mock_client_class.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=yaml_config,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_import_flow_already_configured(hass: HomeAssistant) -> None:
    """Test import flow when entry already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Entur NSR:StopPlace:548",
        data={
            CONF_STOP_IDS: ["NSR:StopPlace:548"],
        },
        unique_id="NSR:StopPlace:548",
    )
    entry.add_to_hass(hass)

    yaml_config = {
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
        CONF_EXPAND_PLATFORMS: True,
        CONF_NAME: "My Bus Stop",
        "show_on_map": False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }

    with patch(
        "homeassistant.components.entur_public_transport.config_flow.EnturPublicTransportData"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client.update = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=yaml_config,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
