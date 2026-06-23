"""Tests for the LG Infrared config flow."""

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.lg_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_HVAC_MODES,
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

# ── TV flow ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("tv_config", "expected_title"),
    [
        pytest.param(
            {CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id},
            "LG TV via Test IR emitter",
            id="emitter_only",
        ),
        pytest.param(
            {
                CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
                CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id,
            },
            "LG TV via Test IR emitter",
            id="emitter_and_receiver",
        ),
        pytest.param(
            {CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id},
            "LG TV via Test IR receiver",
            id="receiver_only",
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_user_flow_tv_success(
    hass: HomeAssistant,
    tv_config: dict[str, str],
    expected_title: str,
) -> None:
    """Test successful TV config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE_TYPE: LGDeviceType.TV}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "tv"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=tv_config
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["data"] == {CONF_DEVICE_TYPE: LGDeviceType.TV, **tv_config}
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_tv_requires_emitter_or_receiver(
    hass: HomeAssistant,
) -> None:
    """Test TV flow shows error when neither emitter nor receiver is selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE_TYPE: LGDeviceType.TV}
    )

    assert result["step_id"] == "tv"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_infrared_entity"}


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param(
            {CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id},
            id="emitter_conflict",
        ),
        pytest.param(
            {CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id},
            id="receiver_conflict",
        ),
        pytest.param(
            {
                CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
                CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id,
            },
            id="both_conflict",
        ),
    ],
)
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    user_input: dict[str, str],
) -> None:
    """Test TV flow aborts when entry is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE_TYPE: LGDeviceType.TV}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("init_infrared")
async def test_user_flow_no_emitters_receivers(hass: HomeAssistant) -> None:
    """Test flow aborts when no infrared emitters or receivers exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_entities"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
@pytest.mark.parametrize(
    ("entity_name", "expected_title"),
    [
        pytest.param(None, "LG TV via Test IR emitter", id="original_name"),
        pytest.param("AC IR emitter", "LG TV via AC IR emitter", id="custom_name"),
    ],
)
async def test_user_flow_tv_title_from_entity_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_name: str | None,
    expected_title: str,
) -> None:
    """Test TV config entry title uses the entity name."""
    entity_registry.async_update_entity(
        mock_infrared_emitter_entity_id, name=entity_name
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE_TYPE: LGDeviceType.TV}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title


# ── AC flow ───────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_ac_success(hass: HomeAssistant) -> None:
    """Test successful AC config flow with default modes (cool + dry)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE_TYPE: LGDeviceType.AC}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ac"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LG AC via Test IR emitter"
    assert result["data"] == {
        CONF_DEVICE_TYPE: LGDeviceType.AC,
        CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
        CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
    }
    assert result["result"].unique_id is None


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_user_flow_ac_with_heat_and_receiver(hass: HomeAssistant) -> None:
    """Test AC flow with heat mode and optional receiver."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE_TYPE: LGDeviceType.AC}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
            CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HVAC_MODES] == [
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
    ]
    assert result["data"][CONF_INFRARED_RECEIVER_ENTITY_ID] == (
        mock_infrared_receiver_entity_id
    )


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_ac_already_configured(
    hass: HomeAssistant, mock_ac_config_entry: MockConfigEntry
) -> None:
    """Test AC flow aborts when entry is already configured."""
    mock_ac_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE_TYPE: LGDeviceType.AC}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
