"""Test the LED Infrared config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.led_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    LEDIrDeviceType,
)
from homeassistant.components.led_infrared.entity import CODES
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry
from tests.components.infrared import EMITTER_ENTITY_ID, RECEIVER_ENTITY_ID
from tests.components.infrared.common import MockInfraredEmitterEntity


@pytest.fixture(autouse=True)
def mock_toggle_gap() -> Generator[None]:
    """Set the toggle gap to 0 so the test step doesn't actually wait."""
    with patch("homeassistant.components.led_infrared.config_flow._TOGGLE_GAP", 0):
        yield


@pytest.mark.parametrize(
    ("device_type", "device_name"),
    [
        (LEDIrDeviceType.GENERIC_13_KEY, "13-key remote"),
        (LEDIrDeviceType.GENERIC_24_KEY, "24-key remote"),
        (LEDIrDeviceType.GENERIC_40_KEY, "40-key remote"),
        (LEDIrDeviceType.GENERIC_44_KEY, "44-key remote"),
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    device_type: LEDIrDeviceType,
    device_name: str,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_TYPE: device_type,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
            CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"LED light with {device_name} via Test IR emitter"
    assert result["data"] == {
        CONF_DEVICE_TYPE: device_type,
        CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "user_input",
    [
        {
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
        {
            CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
        },
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_form_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    user_input: dict[str, str],
) -> None:
    """Test we abort when already configured."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_24_KEY,
            **user_input,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_user_flow_requires_emitter_or_receiver(
    hass: HomeAssistant,
) -> None:
    """Test user flow requires an infrared emitter or receiver."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_24_KEY},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_infrared_entity"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_24_KEY,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("init_infrared")
async def test_user_flow_no_emitters_receivers(hass: HomeAssistant) -> None:
    """Test user flow aborts when no infrared emitters or receivers exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_entities"


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_flow_reconfigure(hass: HomeAssistant) -> None:
    """Test reconfigure flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="LED Infrared via Test IR emitter",
        entry_id="1234567890",
        data={
            CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_24_KEY,
            CONF_INFRARED_ENTITY_ID: None,
        },
    )
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_INFRARED_ENTITY_ID] == EMITTER_ENTITY_ID

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_reconfigure_flow_requires_emitter(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow requires an infrared emitter."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_infrared_entity"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    "user_input",
    [
        {
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
        {
            CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
        },
    ],
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_flow_reconfigure_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry, user_input: dict[str, str]
) -> None:
    """Test reconfigure flow."""
    config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        title="LED Infrared via Test IR emitter",
        entry_id="0987654321",
        data={CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_24_KEY},
    )
    config_entry.add_to_hass(hass)
    config_entry_2.add_to_hass(hass)
    result = await config_entry_2.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("init_infrared")
async def test_reconfigure_flow_no_emitters(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow aborts when no infrared emitters exist."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_entities"


@pytest.mark.parametrize(
    ("next_variant_presses", "expected_device_type", "expected_address"),
    [
        pytest.param(0, LEDIrDeviceType.GENERIC_10_KEY, 0xFF00, id="first"),
        pytest.param(1, LEDIrDeviceType.GENERIC_10_KEY_B708, 0xB708, id="second"),
        pytest.param(2, LEDIrDeviceType.GENERIC_10_KEY, 0xFF00, id="wrap_around"),
    ],
)
@pytest.mark.usefixtures("mock_infrared_receiver_entity")
async def test_form_10_key_test_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    next_variant_presses: int,
    expected_device_type: LEDIrDeviceType,
    expected_address: int,
) -> None:
    """Test the 10-key remote flow tests code sets until the light reacts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert (
        LEDIrDeviceType.GENERIC_10_KEY_B708
        not in (result["data_schema"].schema[CONF_DEVICE_TYPE].config["options"])
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_10_KEY,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
            CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
        },
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "test_device"
    assert result["description_placeholders"] == {
        "variant": "1",
        "variant_count": "2",
    }

    for _ in range(next_variant_presses):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "next_variant"}
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "test_device"

    # The last test toggled the light on and then off again
    sent = mock_infrared_emitter_entity.send_command_calls[-2:]
    assert [(command.address, command.command) for command in sent] == [
        (expected_address, CODES[expected_device_type].ON.value),
        (expected_address, CODES[expected_device_type].OFF.value),
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LED light with 10-key remote via Test IR emitter"
    assert result["data"] == {
        CONF_DEVICE_TYPE: expected_device_type,
        CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_setup_entry")
async def test_form_10_key_test_device_send_failed(hass: HomeAssistant) -> None:
    """Test the 10-key remote flow recovers when sending the test fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.led_infrared.config_flow.async_send_command",
        side_effect=HomeAssistantError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_10_KEY,
                CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
            },
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "test_failed"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "test_device"}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "test_device"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_10_KEY,
        CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
    }


@pytest.mark.usefixtures("mock_infrared_receiver_entity", "mock_setup_entry")
async def test_form_10_key_receiver_only(hass: HomeAssistant) -> None:
    """Test the 10-key remote flow skips the test without an emitter."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_10_KEY,
            CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LED light with 10-key remote via Test IR receiver"
    assert result["data"] == {
        CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_10_KEY,
        CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
    }


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_form_10_key_already_configured(hass: HomeAssistant) -> None:
    """Test the 10-key remote flow aborts when the tested code set is configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_10_KEY_B708,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_TYPE: LEDIrDeviceType.GENERIC_10_KEY,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "next_variant"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
