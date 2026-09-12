"""Tests for the OSRAM infrared config flow."""

from unittest.mock import patch

import pytest

from homeassistant.components.osram_infrared.const import (
    CONF_IR_EMITTER_ENTITY_ID,
    CONF_IR_RECEIVER_ENTITY_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.infrared import (
    EMITTER_ENTITY_ID as MOCK_INFRARED_EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID as MOCK_INFRARED_RECEIVER_ENTITY_ID,
)


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity",
    "mock_infrared_receiver_entity",
)
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IR_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
            CONF_IR_RECEIVER_ENTITY_ID: MOCK_INFRARED_RECEIVER_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OSRAM light via Test IR emitter"
    assert result["data"] == {
        CONF_IR_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
        CONF_IR_RECEIVER_ENTITY_ID: MOCK_INFRARED_RECEIVER_ENTITY_ID,
    }


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user flow aborts when the emitter is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IR_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("init_infrared")
async def test_user_flow_no_emitters(hass: HomeAssistant) -> None:
    """Test user flow aborts when no infrared emitter exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
@pytest.mark.parametrize(
    ("entity_name", "expected_title"),
    [
        (None, "OSRAM light via Test IR emitter"),
        ("Living room IR emitter", "OSRAM light via Living room IR emitter"),
    ],
)
async def test_user_flow_title_from_entity_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_name: str | None,
    expected_title: str,
) -> None:
    """Test config-entry title uses the infrared emitter name."""
    entity_registry.async_update_entity(
        MOCK_INFRARED_EMITTER_ENTITY_ID,
        name=entity_name,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IR_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_without_receiver(hass: HomeAssistant) -> None:
    """Test successful setup without an infrared receiver."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_IR_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_IR_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
    }


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_stale_emitter_selection(
    hass: HomeAssistant,
) -> None:
    """Test user flow rejects an emitter that disappears before submit."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.osram_infrared.config_flow.async_get_emitters",
        return_value=["infrared.other_emitter"],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_IR_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {
        CONF_IR_EMITTER_ENTITY_ID: "cannot_connect",
    }


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity",
    "mock_infrared_receiver_entity",
)
async def test_user_flow_stale_receiver_selection(
    hass: HomeAssistant,
) -> None:
    """Test user flow rejects a receiver that disappears before submit."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.osram_infrared.config_flow.async_get_receivers",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_IR_EMITTER_ENTITY_ID: MOCK_INFRARED_EMITTER_ENTITY_ID,
                CONF_IR_RECEIVER_ENTITY_ID: MOCK_INFRARED_RECEIVER_ENTITY_ID,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {
        CONF_IR_RECEIVER_ENTITY_ID: "cannot_connect",
    }


async def test_user_flow_uses_entity_id_as_title_fallback(
    hass: HomeAssistant,
) -> None:
    """Test user flow uses the emitter entity ID when it is missing from registry."""
    emitter_entity_id = "infrared.missing_registry_emitter"

    with (
        patch(
            "homeassistant.components.osram_infrared.config_flow.async_get_emitters",
            return_value=[emitter_entity_id],
        ),
        patch(
            "homeassistant.components.osram_infrared.config_flow.er.async_get",
        ) as mock_async_get_entity_registry,
    ):
        mock_async_get_entity_registry.return_value.async_get.return_value = None

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_IR_EMITTER_ENTITY_ID: emitter_entity_id,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"OSRAM light via {emitter_entity_id}"
    assert result["data"] == {
        CONF_IR_EMITTER_ENTITY_ID: emitter_entity_id,
    }
