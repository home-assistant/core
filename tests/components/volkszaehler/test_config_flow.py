"""Test config flow for Volkszaehler integration."""

from unittest.mock import AsyncMock

import pytest
from volkszaehler.exceptions import (
    VolkszaehlerApiConnectionError,
    VolkszaehlerNoDataAvailable,
)

from homeassistant.components.volkszaehler.const import DOMAIN, SUBENTRY_TYPE_CHANNEL
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_UUID,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_create_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api: AsyncMock,
) -> None:
    """Test that the config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_UUID: "test-uuid",
            CONF_HOST: "localhost",
            CONF_PORT: 80,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "localhost"
    assert result["data"] == {
        CONF_HOST: "localhost",
        CONF_PORT: 80,
    }

    entry = result["result"]
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_TYPE_CHANNEL
    assert subentry.title == "test-uuid"
    assert subentry.unique_id == "test-uuid"
    assert subentry.data == {CONF_UUID: "test-uuid"}

    assert mock_api.get_data.call_count == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (VolkszaehlerApiConnectionError, "cannot_connect"),
        (VolkszaehlerNoDataAvailable, "no_data"),
        (Exception, "unknown"),
    ],
)
async def test_user_errors(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test error handling in the config flow user step."""
    user_input = {
        CONF_UUID: "test-uuid",
        CONF_HOST: "localhost",
        CONF_PORT: 80,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    mock_api.get_data.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    mock_api.get_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "localhost"
    assert result["data"] == {
        CONF_HOST: "localhost",
        CONF_PORT: 80,
    }


async def test_create_subentry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test that the subentry flow creates an additional channel."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_CHANNEL),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_UUID: "new-uuid"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "new-uuid"
    assert result["data"] == {CONF_UUID: "new-uuid"}
    assert len(mock_config_entry.subentries) == 2

    assert mock_api.get_data.call_count == 1


async def test_import(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Test that we can import a config entry."""
    import_data = {
        CONF_UUID: "import-uuid",
        CONF_HOST: "importhost",
        CONF_NAME: "2.8.0",
        CONF_PLATFORM: "volkszaehler",
        CONF_MONITORED_CONDITIONS: ["consumption"],
    }
    await async_setup_component(hass, "sensor", {"sensor": import_data})

    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.data == {
        CONF_HOST: "importhost",
        CONF_PORT: 80,
    }
    assert entry.title == "importhost"
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type is SUBENTRY_TYPE_CHANNEL
    assert subentry.title == "2.8.0"
    assert subentry.data == {CONF_UUID: "import-uuid"}

    assert mock_api.get_data.call_count == 2


async def test_import_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test that we import a config entry only once."""
    mock_config_entry.add_to_hass(hass)

    import_data = {
        CONF_UUID: "existing-uuid",
        CONF_HOST: "localhost",
        CONF_PORT: 80,
        CONF_PLATFORM: "volkszaehler",
    }
    await async_setup_component(hass, "sensor", {"sensor": import_data})

    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].entry_id == mock_config_entry.entry_id
    assert len(entries[0].subentries) == 1

    assert mock_api.get_data.call_count == 1


async def test_import_add_second_subentry_same_host(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """Test that import adds a second channel to the existing entry on same host."""
    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    CONF_UUID: "import-uuid-1",
                    CONF_HOST: "importhost",
                    CONF_PORT: 8080,
                    CONF_PLATFORM: "volkszaehler",
                },
                {
                    CONF_UUID: "import-uuid-2",
                    CONF_HOST: "importhost",
                    CONF_PORT: 8080,
                    CONF_PLATFORM: "volkszaehler",
                },
            ]
        },
    )

    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert len(entries[0].subentries) == 2

    assert mock_api.get_data.call_count == 3


async def test_import_validation_error(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """Test that import aborts when input validation fails."""
    mock_api.get_data.side_effect = VolkszaehlerApiConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "import"},
        data={
            CONF_UUID: "import-uuid",
            CONF_HOST: "importhost",
            CONF_PORT: 80,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_duplicate_uuid_from_entry_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test user flow duplicate UUID detection from an entry unique_id."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_UUID: "existing-uuid",
            CONF_HOST: "new-host",
            CONF_PORT: 80,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_api.get_data.call_count == 1


async def test_subentry_duplicate_uuid(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that subentry flow aborts for duplicate UUID."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_CHANNEL),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_UUID: "existing-uuid"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_subentry_validation_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test that subentry flow returns form error on validation failure."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_CHANNEL),
        context={"source": SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM

    mock_api.get_data.side_effect = VolkszaehlerApiConnectionError
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_UUID: "new-uuid"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"
