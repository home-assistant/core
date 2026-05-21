"""Tests for the Virtual Remote config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.virtual_remote.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from .conftest import INFRARED_ENTITY_ID

from tests.common import MockConfigEntry


async def test_user_flow_no_infrared_entities(hass: HomeAssistant) -> None:
    """Test abort when no infrared entities exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is config_entries.FlowResultType.ABORT
    assert result["reason"] == "no_available_infrared_entities"


async def test_user_flow_success(hass: HomeAssistant, infrared_entity: str) -> None:
    """Test successful setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is config_entries.FlowResultType.FORM

    with patch(
        "homeassistant.components.virtual_remote.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_REMOTE_NAME: "Living Room TV",
                CONF_INFRARED_ENTITY_ID: infrared_entity,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is config_entries.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Virtual Remote"
    assert result["options"] == {
        CONF_VIRTUAL_REMOTES: [
            {
                CONF_REMOTE_ID: "living_room_tv",
                CONF_REMOTE_NAME: "Living Room TV",
                CONF_INFRARED_ENTITY_ID: infrared_entity,
            }
        ]
    }
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        (
            {
                CONF_REMOTE_NAME: "",
                CONF_INFRARED_ENTITY_ID: INFRARED_ENTITY_ID,
            },
            {CONF_REMOTE_NAME: "remote_name_required"},
        ),
        (
            {
                CONF_REMOTE_NAME: "Living Room TV",
                CONF_INFRARED_ENTITY_ID: "infrared.missing",
            },
            {CONF_INFRARED_ENTITY_ID: "infrared_entity_unavailable"},
        ),
    ],
)
async def test_user_flow_validation_errors(
    hass: HomeAssistant,
    infrared_entity: str,
    user_input: dict[str, str],
    errors: dict[str, str],
) -> None:
    """Test setup validation errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is config_entries.FlowResultType.FORM
    assert result["errors"] == errors


async def test_user_flow_single_instance(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test only one config entry is allowed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is config_entries.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring the first remote."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": config_entry.entry_id,
        },
    )
    assert result["type"] is config_entries.FlowResultType.FORM

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload",
        return_value=None,
    ) as mock_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_REMOTE_NAME: "Bedroom TV",
                CONF_INFRARED_ENTITY_ID: INFRARED_ENTITY_ID,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is config_entries.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert (
        config_entry.options[CONF_VIRTUAL_REMOTES][0][CONF_REMOTE_NAME] == "Bedroom TV"
    )
    assert len(mock_reload.mock_calls) == 1


async def test_reconfigure_validation_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure validation errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": config_entry.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_REMOTE_NAME: "",
            CONF_INFRARED_ENTITY_ID: "infrared.missing",
        },
    )

    assert result["type"] is config_entries.FlowResultType.FORM
    assert result["errors"] == {
        CONF_REMOTE_NAME: "remote_name_required",
        CONF_INFRARED_ENTITY_ID: "infrared_entity_unavailable",
    }


async def test_reconfigure_no_remotes(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test reconfigure aborts when no remotes are configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Virtual Remote",
        data={},
        options={CONF_VIRTUAL_REMOTES: []},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] is config_entries.FlowResultType.ABORT
    assert result["reason"] == "no_virtual_remotes"
