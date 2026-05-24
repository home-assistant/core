"""Test the Kaku RC config flow."""

from homeassistant.components.klik_aan_klik_uit_rc.const import (
    CONF_CHANNEL,
    CONF_DEVICE_ID,
    CONF_DIM,
    CONF_GROUP,
    CONF_TRANSMITTER,
    DOMAIN,
)
from homeassistant.components.radio_frequency import DATA_COMPONENT, DOMAIN as RF_DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .conftest import TRANSMITTER_ENTITY_ID

from tests.common import MockConfigEntry
from tests.components.radio_frequency.common import MockRadioFrequencyEntity


async def _start_user_flow(hass: HomeAssistant) -> dict:
    """Start user flow and assert first form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def test_user_flow(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> None:
    """Test successful user flow creates an entry."""
    result = await _start_user_flow(hass)

    user_input = {
        CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
        CONF_DEVICE_ID: 123456,
        CONF_CHANNEL: 1,
        CONF_GROUP: False,
        CONF_DIM: False,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_mode"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert len(mock_rf_entity.send_command_calls) == 1
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_result"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device_responded": True}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kaku ID 123456 CH 1"
    assert result["data"] == user_input


async def test_user_flow_retry_learn(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> None:
    """Test the user can retry pairing when the device does not respond."""
    result = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
            CONF_DEVICE_ID: 123456,
            CONF_CHANNEL: 1,
            CONF_GROUP: False,
            CONF_DIM: False,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_mode"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert len(mock_rf_entity.send_command_calls) == 1
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_result"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device_responded": False}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_mode"
    assert result["errors"] == {"base": "no_response"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert len(mock_rf_entity.send_command_calls) == 2
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pairing_result"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device_responded": True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_invalid_device_id(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> None:
    """Test validation for invalid device ID."""
    result = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
            CONF_DEVICE_ID: -1,
            CONF_CHANNEL: 1,
            CONF_GROUP: False,
            CONF_DIM: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_DEVICE_ID: "invalid_device_id"}


async def test_invalid_channel(
    hass: HomeAssistant, mock_rf_entity: MockRadioFrequencyEntity
) -> None:
    """Test validation for invalid channel."""
    result = await _start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
            CONF_DEVICE_ID: 123456,
            CONF_CHANNEL: 17,
            CONF_GROUP: False,
            CONF_DIM: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_CHANNEL: "invalid_channel"}


async def test_unique_id_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when same transmitter/id/channel/group is configured."""
    mock_config_entry.add_to_hass(hass)

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRANSMITTER: TRANSMITTER_ENTITY_ID,
            CONF_DEVICE_ID: 123456,
            CONF_CHANNEL: 1,
            CONF_GROUP: False,
            CONF_DIM: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_no_transmitters(hass: HomeAssistant) -> None:
    """Test flow aborts when no RF transmitters are set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_transmitters"


async def test_no_compatible_transmitters(hass: HomeAssistant) -> None:
    """Test aborting when transmitters exist but none support 433.92 MHz OOK."""
    assert await async_setup_component(hass, RF_DOMAIN, {})
    await hass.async_block_till_done()
    incompatible = MockRadioFrequencyEntity(
        "incompatible", frequency_ranges=[(868_000_000, 869_000_000)]
    )
    await hass.data[DATA_COMPONENT].async_add_entities([incompatible])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_compatible_transmitters"
