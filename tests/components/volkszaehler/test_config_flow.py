"""Test config flow for Volkszaehler integration."""

from unittest.mock import AsyncMock, patch

import pytest
from volkszaehler.exceptions import (
    VolkszaehlerApiConnectionError,
    VolkszaehlerNoDataAvailable,
)

from homeassistant.components.volkszaehler import sensor
from homeassistant.components.volkszaehler.const import DOMAIN, SUBENTRY_TYPE_CHANNEL
from homeassistant.config_entries import ConfigSubentryData
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

from tests.common import MockConfigEntry


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test that the config flow creates an entry."""
    user_input = {
        CONF_UUID: "test-uuid",
        CONF_HOST: "localhost",
        CONF_PORT: 80,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("volkszaehler.Volkszaehler.get_data", new_callable=AsyncMock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
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


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (VolkszaehlerApiConnectionError, "cannot_connect"),
        (VolkszaehlerNoDataAvailable, "no_data"),
        (Exception, "unknown"),
    ],
)
async def test_user_errors(
    hass: HomeAssistant, side_effect: type[Exception], expected_error: str
) -> None:
    """Test error handling in the config flow user step."""
    user_input = {
        CONF_UUID: "test-uuid",
        CONF_HOST: "localhost",
        CONF_PORT: 80,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM

    with patch("volkszaehler.Volkszaehler.get_data", side_effect=side_effect):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    with patch("volkszaehler.Volkszaehler.get_data", new_callable=AsyncMock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "localhost"
    assert result["data"] == {
        CONF_HOST: "localhost",
        CONF_PORT: 80,
    }


async def test_create_subentry(hass: HomeAssistant) -> None:
    """Test that the subentry flow creates an additional channel."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="localhost",
        data={
            CONF_HOST: "localhost",
            CONF_PORT: 80,
        },
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_CHANNEL,
                title="existing-uuid",
                data={CONF_UUID: "existing-uuid"},
                unique_id="existing-uuid",
                subentry_id="existing-subentry-id",
            )
        ],
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_CHANNEL), context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("volkszaehler.Volkszaehler.get_data", new_callable=AsyncMock):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_UUID: "new-uuid"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "new-uuid"
    assert result["data"] == {CONF_UUID: "new-uuid"}
    assert len(entry.subentries) == 2


async def test_import(hass: HomeAssistant) -> None:
    """Test that we can import a config entry."""
    import_data = {
        CONF_UUID: "import-uuid",
        CONF_HOST: "importhost",
        CONF_NAME: "2.8.0",
        CONF_PLATFORM: "volkszaehler",
        CONF_MONITORED_CONDITIONS: ["consumption"],
    }
    with patch("volkszaehler.Volkszaehler.get_data", new_callable=AsyncMock):
        await sensor.async_setup_platform(hass, import_data, None)

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
    assert subentry.subentry_type == SUBENTRY_TYPE_CHANNEL
    assert subentry.title == "2.8.0"
    assert subentry.data == {CONF_UUID: "import-uuid"}


async def test_import_once(hass: HomeAssistant) -> None:
    """Test that we import a config entry only once."""
    import_data = {
        CONF_UUID: "import-uuid",
        CONF_HOST: "importhost",
        CONF_PORT: 8080,
        CONF_PLATFORM: "volkszaehler",
    }
    with patch("volkszaehler.Volkszaehler.get_data", new_callable=AsyncMock):
        await sensor.async_setup_platform(hass, import_data, None)
        await sensor.async_setup_platform(hass, import_data, None)

    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert len(entries[0].subentries) == 1


async def test_import_add_second_subentry_same_host(hass: HomeAssistant) -> None:
    """Test that import adds a second channel to the existing entry on same host."""
    with patch("volkszaehler.Volkszaehler.get_data", new_callable=AsyncMock):
        await sensor.async_setup_platform(
            hass,
            {
                CONF_UUID: "import-uuid-1",
                CONF_HOST: "importhost",
                CONF_PORT: 8080,
                CONF_PLATFORM: "volkszaehler",
            },
            None,
        )
        await sensor.async_setup_platform(
            hass,
            {
                CONF_UUID: "import-uuid-2",
                CONF_HOST: "importhost",
                CONF_PORT: 8080,
                CONF_PLATFORM: "volkszaehler",
            },
            None,
        )

    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert len(entries[0].subentries) == 2


async def test_import_validation_error(hass: HomeAssistant) -> None:
    """Test that import aborts when input validation fails."""
    with patch(
        "volkszaehler.Volkszaehler.get_data",
        side_effect=VolkszaehlerApiConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={
                CONF_UUID: "import-uuid",
                CONF_HOST: "importhost",
                CONF_PORT: 80,
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_duplicate_uuid_from_entry_unique_id(hass: HomeAssistant) -> None:
    """Test user flow duplicate UUID detection from an entry unique_id."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="existing",
        data={
            CONF_HOST: "existing-host",
            CONF_PORT: 80,
        },
        unique_id="duplicate-uuid",
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM

    with patch("volkszaehler.Volkszaehler.get_data", new_callable=AsyncMock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_UUID: "duplicate-uuid",
                CONF_HOST: "new-host",
                CONF_PORT: 80,
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_subentry_duplicate_uuid(hass: HomeAssistant) -> None:
    """Test that subentry flow aborts for duplicate UUID."""
    parent_entry = MockConfigEntry(
        domain=DOMAIN,
        title="localhost",
        data={
            CONF_HOST: "localhost",
            CONF_PORT: 80,
        },
    )
    parent_entry.add_to_hass(hass)

    existing = MockConfigEntry(
        domain=DOMAIN,
        title="other",
        data={
            CONF_HOST: "other-host",
            CONF_PORT: 80,
        },
        unique_id="duplicate-subentry-uuid",
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (parent_entry.entry_id, SUBENTRY_TYPE_CHANNEL), context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_UUID: "duplicate-subentry-uuid"},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_subentry_validation_error(hass: HomeAssistant) -> None:
    """Test that subentry flow returns form error on validation failure."""
    parent_entry = MockConfigEntry(
        domain=DOMAIN,
        title="localhost",
        data={
            CONF_HOST: "localhost",
            CONF_PORT: 80,
        },
    )
    parent_entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (parent_entry.entry_id, SUBENTRY_TYPE_CHANNEL), context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM

    with patch(
        "volkszaehler.Volkszaehler.get_data",
        side_effect=VolkszaehlerApiConnectionError,
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_UUID: "new-uuid"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"
