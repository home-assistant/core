"""Tests for the Virtual Remote config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.virtual_remote.config_flow import VirtualRemoteConfigFlow
from homeassistant.components.virtual_remote.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import INFRARED_ENTITY_ID

from tests.common import MockConfigEntry


async def test_user_flow_no_infrared_entities(hass: HomeAssistant) -> None:
    """Test abort when no infrared entities exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_available_infrared_entities"


async def test_user_flow_success(hass: HomeAssistant, infrared_entity: str) -> None:
    """Test successful setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

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

    assert result["type"] is FlowResultType.CREATE_ENTRY
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

    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.ABORT
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
    assert result["type"] is FlowResultType.FORM

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

    assert result["type"] is FlowResultType.ABORT
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
            CONF_INFRARED_ENTITY_ID: INFRARED_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_REMOTE_NAME: "remote_name_required"}


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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_virtual_remotes"


async def test_user_flow_aborts_without_infrared_entities(
    hass: HomeAssistant,
) -> None:
    """Test user flow aborts when no infrared entities are available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_available_infrared_entities"


async def test_reconfigure_aborts_without_virtual_remotes(
    hass: HomeAssistant,
) -> None:
    """Test reconfigure aborts when no virtual remotes are configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_VIRTUAL_REMOTES: []},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_virtual_remotes"


async def test_reconfigure_aborts_without_available_infrared_entities(
    hass: HomeAssistant,
) -> None:
    """Test reconfigure aborts when no infrared entities are available."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_VIRTUAL_REMOTES: [
                {
                    CONF_REMOTE_ID: "living_room_tv",
                    CONF_REMOTE_NAME: "Living Room TV",
                    CONF_INFRARED_ENTITY_ID: "infrared.missing",
                }
            ]
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_available_infrared_entities"


async def test_user_flow_aborts_without_available_infrared_entities(
    hass: HomeAssistant,
) -> None:
    """Test user flow aborts when no infrared entities are available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_available_infrared_entities"


async def test_direct_user_step_rejects_unavailable_infrared_entity(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test user step handles unavailable selected infrared entity."""
    flow = VirtualRemoteConfigFlow()
    flow.hass = hass

    with (
        patch(
            "homeassistant.components.virtual_remote.config_flow.available_infrared_entities",
            return_value={"infrared.test_ir": "Test IR"},
        ),
        patch.object(flow, "async_set_unique_id", AsyncMock(return_value=None)),
        patch.object(flow, "_abort_if_unique_id_configured", return_value=None),
    ):
        result = await flow.async_step_user(
            {
                CONF_REMOTE_NAME: "Living Room TV",
                CONF_INFRARED_ENTITY_ID: "infrared.missing",
            }
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_INFRARED_ENTITY_ID: "infrared_entity_unavailable"}


async def test_direct_reconfigure_step_rejects_unavailable_infrared_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    infrared_entity: str,
) -> None:
    """Test reconfigure step handles unavailable selected infrared entity."""
    config_entry.add_to_hass(hass)

    flow = VirtualRemoteConfigFlow()
    flow.hass = hass

    with (
        patch.object(flow, "_get_reconfigure_entry", return_value=config_entry),
        patch(
            "homeassistant.components.virtual_remote.config_flow.available_infrared_entities",
            return_value={"infrared.test_ir": "Test IR"},
        ),
    ):
        result = await flow.async_step_reconfigure(
            {
                CONF_REMOTE_NAME: "Bedroom TV",
                CONF_INFRARED_ENTITY_ID: "infrared.missing",
            }
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_INFRARED_ENTITY_ID: "infrared_entity_unavailable"}
