"""Tests for the LG Infrared config flow."""

import pytest

from homeassistant.components.lg_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    LGDeviceType,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.infrared import (
    EMITTER_ENTITY_ID as mock_infrared_emitter_entity_id,
    RECEIVER_ENTITY_ID as mock_infrared_receiver_entity_id,
)


@pytest.mark.parametrize(
    ("config", "expected_title", "unique_id_entity_id"),
    [
        (
            {CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id},
            "LG TV via Test IR emitter",
            mock_infrared_emitter_entity_id,
        ),
        (
            {
                CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
                CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id,
            },
            "LG TV via Test IR emitter",
            mock_infrared_emitter_entity_id,
        ),
        (
            {CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id},
            "LG TV via Test IR receiver",
            mock_infrared_receiver_entity_id,
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_user_flow_success(
    hass: HomeAssistant,
    config: dict[str, str],
    expected_title: str,
    unique_id_entity_id: str,
) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_TYPE: LGDeviceType.TV, **config},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["data"] == {CONF_DEVICE_TYPE: LGDeviceType.TV, **config}
    assert result["result"].unique_id == f"lg_ir_tv_{unique_id_entity_id}"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_requires_emitter_or_receiver(
    hass: HomeAssistant,
) -> None:
    """Test user flow requires an infrared emitter or receiver."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_TYPE: LGDeviceType.TV},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_infrared_entity"}


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow aborts when entry is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_TYPE: LGDeviceType.TV,
            CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("init_infrared")
async def test_user_flow_no_emitters_receivers(hass: HomeAssistant) -> None:
    """Test user flow aborts when no infrared emitters or receivers exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_entities"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
@pytest.mark.parametrize(
    ("entity_name", "expected_title"),
    [
        (None, "LG TV via Test IR emitter"),
        ("AC IR emitter", "LG TV via AC IR emitter"),
    ],
)
async def test_user_flow_title_from_entity_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_name: str | None,
    expected_title: str,
) -> None:
    """Test config entry title uses the entity name."""
    entity_registry.async_update_entity(
        mock_infrared_emitter_entity_id, name=entity_name
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_TYPE: LGDeviceType.TV,
            CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
