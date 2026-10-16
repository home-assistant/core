"""Tests for the LG Infrared config flow."""

from typing import Any

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.infrared import DATA_COMPONENT as INFRARED_DATA_COMPONENT
from homeassistant.components.lg_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_HVAC_MODES,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    LGDeviceType,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, get_schema_suggested_value
from tests.components.infrared import (
    EMITTER_ENTITY_ID as mock_infrared_emitter_entity_id,
    RECEIVER_ENTITY_ID as mock_infrared_receiver_entity_id,
)
from tests.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)

SECOND_EMITTER_ENTITY_ID = "infrared.second_ir_emitter"
SECOND_RECEIVER_ENTITY_ID = "infrared.second_ir_receiver"


async def _async_start_flow(
    hass: HomeAssistant, device_type: LGDeviceType
) -> ConfigFlowResult:
    """Start the user flow and pick a device type from the menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": device_type.value}
    )


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
    result = await _async_start_flow(hass, LGDeviceType.TV)

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
    result = await _async_start_flow(hass, LGDeviceType.TV)

    assert result["step_id"] == "tv"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_infrared_entity"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


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

    result = await _async_start_flow(hass, LGDeviceType.TV)
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


@pytest.mark.usefixtures("mock_infrared_receiver_entity")
async def test_user_flow_menu_hides_ac_without_emitter(hass: HomeAssistant) -> None:
    """Test the AC option is hidden when only a receiver is available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [LGDeviceType.TV.value]


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

    result = await _async_start_flow(hass, LGDeviceType.TV)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_user_flow_ac_success(hass: HomeAssistant) -> None:
    """Test successful AC config flow with default modes (cool + dry)."""
    result = await _async_start_flow(hass, LGDeviceType.AC)

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
    result = await _async_start_flow(hass, LGDeviceType.AC)
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
async def test_user_flow_ac_requires_hvac_mode(hass: HomeAssistant) -> None:
    """Test AC flow rejects an empty list of supported modes."""
    result = await _async_start_flow(hass, LGDeviceType.AC)

    with pytest.raises(InvalidData) as err:
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
                CONF_HVAC_MODES: [],
            },
        )

    assert err.value.schema_errors == {CONF_HVAC_MODES: "no_hvac_modes"}


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
@pytest.mark.parametrize("device_type", [LGDeviceType.AC])
@pytest.mark.parametrize("has_receiver", [False])
async def test_user_flow_ac_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test AC flow aborts when entry is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await _async_start_flow(hass, LGDeviceType.AC)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.fixture
async def mock_second_infrared_entities(
    hass: HomeAssistant, init_infrared: None
) -> None:
    """Add a second infrared emitter and receiver to choose from."""
    await hass.data[INFRARED_DATA_COMPONENT].async_add_entities(
        [
            MockInfraredEmitterEntity("second_ir_emitter", name="Second IR emitter"),
            MockInfraredReceiverEntity("second_ir_receiver", name="Second IR receiver"),
        ]
    )


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
@pytest.mark.parametrize(
    ("device_type", "expected_hvac_modes"),
    [
        pytest.param(LGDeviceType.TV, None, id="tv"),
        pytest.param(LGDeviceType.AC, [HVACMode.COOL, HVACMode.DRY], id="ac"),
    ],
)
async def test_reconfigure_flow_suggests_current_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    expected_hvac_modes: list[HVACMode] | None,
) -> None:
    """Test the reconfigure form is pre-filled with the current entry data."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    schema = result["data_schema"].schema
    assert (
        get_schema_suggested_value(schema, CONF_INFRARED_ENTITY_ID)
        == mock_infrared_emitter_entity_id
    )
    assert (
        get_schema_suggested_value(schema, CONF_INFRARED_RECEIVER_ENTITY_ID)
        == mock_infrared_receiver_entity_id
    )
    assert get_schema_suggested_value(schema, CONF_HVAC_MODES) == expected_hvac_modes


@pytest.mark.usefixtures("mock_second_infrared_entities")
@pytest.mark.parametrize(
    ("device_type", "has_receiver", "user_input"),
    [
        pytest.param(
            LGDeviceType.TV,
            True,
            {
                CONF_INFRARED_ENTITY_ID: SECOND_EMITTER_ENTITY_ID,
                CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id,
            },
            id="tv_change_emitter",
        ),
        pytest.param(
            LGDeviceType.TV,
            True,
            {CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id},
            id="tv_remove_emitter",
        ),
        pytest.param(
            LGDeviceType.AC,
            False,
            {
                CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
                CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id,
                CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY],
            },
            id="ac_add_receiver_and_mode",
        ),
        pytest.param(
            LGDeviceType.AC,
            True,
            {
                CONF_INFRARED_ENTITY_ID: SECOND_EMITTER_ENTITY_ID,
                CONF_HVAC_MODES: [HVACMode.FAN_ONLY],
            },
            id="ac_change_emitter_remove_receiver",
        ),
    ],
)
async def test_reconfigure_flow(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_type: LGDeviceType,
    user_input: dict[str, Any],
) -> None:
    """Test reconfiguring replaces the entry data and reloads the entry."""
    result = await init_integration.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.data == {CONF_DEVICE_TYPE: device_type, **user_input}
    assert init_integration.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity",
    "mock_infrared_receiver_entity",
    "mock_second_infrared_entities",
)
@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param(
            {
                CONF_INFRARED_ENTITY_ID: SECOND_EMITTER_ENTITY_ID,
                CONF_INFRARED_RECEIVER_ENTITY_ID: mock_infrared_receiver_entity_id,
            },
            id="emitter_conflict",
        ),
        pytest.param(
            {
                CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
                CONF_INFRARED_RECEIVER_ENTITY_ID: SECOND_RECEIVER_ENTITY_ID,
            },
            id="receiver_conflict",
        ),
    ],
)
async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    user_input: dict[str, str],
) -> None:
    """Test reconfigure aborts when another entry uses the chosen IR entity."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_TYPE: LGDeviceType.TV,
            CONF_INFRARED_ENTITY_ID: SECOND_EMITTER_ENTITY_ID,
            CONF_INFRARED_RECEIVER_ENTITY_ID: SECOND_RECEIVER_ENTITY_ID,
        },
    ).add_to_hass(hass)
    original_data = dict(mock_config_entry.data)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == original_data


@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_reconfigure_flow_tv_requires_emitter_or_receiver(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring a TV shows an error when both IR entities are cleared."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_infrared_entity"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_DEVICE_TYPE: LGDeviceType.TV,
        CONF_INFRARED_ENTITY_ID: mock_infrared_emitter_entity_id,
    }


@pytest.mark.usefixtures("init_infrared")
async def test_reconfigure_flow_tv_no_infrared_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring a TV aborts when no infrared entity exists."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_entities"


@pytest.mark.usefixtures("mock_infrared_receiver_entity")
@pytest.mark.parametrize("device_type", [LGDeviceType.AC])
async def test_reconfigure_flow_ac_no_infrared_emitters(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring an AC aborts when only a receiver exists."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"
