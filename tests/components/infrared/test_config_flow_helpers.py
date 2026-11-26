"""Tests for the infrared config flow helpers."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock

import probatio
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID,
)
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.infrared import DATA_COMPONENT, InfraredConsumerConfigFlow
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import device_registry as dr, entity_registry as er

TEST_DOMAIN = "test"
CONF_DEVICE_TYPE = "device_type"
EMITTER_KEY = "emitter_entity_id"
RECEIVER_KEY = "receiver_entity_id"
OTHER_ENTITY_ID = "infrared.other_ir_entity"
OTHER_ENTRY_EMITTER_ENTITY_ID = "infrared.other_entry_ir_emitter"
UNNAMED_EMITTER_ENTITY_ID = "infrared.unnamed_ir_emitter"


class MockInfraredConsumerFlow(InfraredConsumerConfigFlow):
    """Config flow that uses the default infrared steps."""

    INFRARED_EMITTER_KEY = EMITTER_KEY
    INFRARED_RECEIVER_KEY = RECEIVER_KEY

    async def _async_infrared_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return the title of a new entry."""
        return self._async_infrared_entity_name(user_input[EMITTER_KEY])


class MockEmitterOnlyConsumerFlow(MockInfraredConsumerFlow):
    """Config flow for a consumer without an infrared receiver."""

    INFRARED_RECEIVER_KEY = None


class MockDeviceTypeConsumerFlow(MockInfraredConsumerFlow):
    """Config flow with an option to pick a device type in addition to the default ones."""

    @callback
    def _async_infrared_schema(self) -> probatio.Schema:
        """Return the device type and infrared entity schema."""
        return probatio.Schema(
            {
                probatio.Required(CONF_DEVICE_TYPE): str,
                **self._async_infrared_entity_fields(),
            }
        )

    @callback
    def _async_infrared_match_dict(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """Return the device type."""
        return {CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE]}


@pytest.fixture
def consumer_flow() -> type[InfraredConsumerConfigFlow]:
    """Return the mock consumer config flow class to register."""
    return MockInfraredConsumerFlow


@pytest.fixture(autouse=True)
def mock_consumer_flow(
    hass: HomeAssistant, consumer_flow: type[InfraredConsumerConfigFlow]
) -> Generator[None]:
    """Register the mock consumer config flow."""
    mock_integration(
        hass, MockModule(TEST_DOMAIN, async_setup_entry=AsyncMock(return_value=None))
    )
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow", None)
    with mock_config_flow(TEST_DOMAIN, consumer_flow):
        yield


@pytest.fixture
def ignore_translations_for_mock_domains() -> list[str]:
    """Do not validate translations for the mock consumer integration."""
    return [TEST_DOMAIN]


async def _async_run_flow(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> ConfigFlowResult:
    """Start the mock consumer flow and submit the user step."""
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


async def _async_run_reconfigure_flow(
    hass: HomeAssistant, entry: MockConfigEntry, user_input: dict[str, Any]
) -> ConfigFlowResult:
    """Start the mock consumer reconfigure flow and submit it."""
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


@pytest.mark.usefixtures("init_infrared")
async def test_abort_no_emitters(hass: HomeAssistant) -> None:
    """Test the user flow aborts when there are no infrared emitters."""
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"


@pytest.mark.parametrize(
    ("consumer_flow", "user_input"),
    [
        pytest.param(
            MockInfraredConsumerFlow,
            {EMITTER_KEY: EMITTER_ENTITY_ID, RECEIVER_KEY: RECEIVER_ENTITY_ID},
            id="emitter_and_receiver",
        ),
        pytest.param(
            MockInfraredConsumerFlow, {EMITTER_KEY: EMITTER_ENTITY_ID}, id="emitter"
        ),
        pytest.param(
            MockEmitterOnlyConsumerFlow,
            {EMITTER_KEY: EMITTER_ENTITY_ID},
            id="emitter_only_consumer",
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_create_entry(hass: HomeAssistant, user_input: dict[str, str]) -> None:
    """Test creating an entry with the selected infrared entities."""
    result = await _async_run_flow(hass, user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test IR emitter"
    assert result["data"] == user_input


@pytest.mark.parametrize(
    ("consumer_flow", "user_input"),
    [
        pytest.param(
            MockInfraredConsumerFlow,
            {RECEIVER_KEY: RECEIVER_ENTITY_ID},
            id="no_emitter",
        ),
        pytest.param(
            MockInfraredConsumerFlow,
            {EMITTER_KEY: RECEIVER_ENTITY_ID},
            id="receiver_as_emitter",
        ),
        pytest.param(
            MockInfraredConsumerFlow,
            {EMITTER_KEY: EMITTER_ENTITY_ID, RECEIVER_KEY: EMITTER_ENTITY_ID},
            id="emitter_as_receiver",
        ),
        pytest.param(
            MockEmitterOnlyConsumerFlow,
            {EMITTER_KEY: EMITTER_ENTITY_ID, RECEIVER_KEY: RECEIVER_ENTITY_ID},
            id="receiver_on_emitter_only_consumer",
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_invalid_entity_selection(
    hass: HomeAssistant, user_input: dict[str, str]
) -> None:
    """Test the emitter is required and each field only accepts its entity type."""
    with pytest.raises(InvalidData):
        await _async_run_flow(hass, user_input)


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_title_includes_device_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the entry title uses the full name of the emitter entity."""
    hub_entry = MockConfigEntry(domain="hub")
    hub_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=hub_entry.entry_id,
        identifiers={("hub", "living_room")},
        name="Living room hub",
    )
    entity_registry.async_update_entity(EMITTER_ENTITY_ID, device_id=device.id)

    result = await _async_run_flow(hass, {EMITTER_KEY: EMITTER_ENTITY_ID})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room hub Test IR emitter"


@pytest.mark.parametrize(
    "unique_id",
    [
        pytest.param("unnamed_ir_emitter", id="registered_without_name"),
        pytest.param(None, id="not_registered"),
    ],
)
@pytest.mark.usefixtures("init_infrared")
async def test_title_falls_back_to_entity_id(
    hass: HomeAssistant, unique_id: str | None
) -> None:
    """Test the entry title uses the entity ID when the entity has no full name."""
    emitter = MockInfraredEmitterEntity("unnamed_ir_emitter", None)
    emitter._attr_unique_id = unique_id
    emitter.entity_id = UNNAMED_EMITTER_ENTITY_ID
    await hass.data[DATA_COMPONENT].async_add_entities([emitter])

    result = await _async_run_flow(hass, {EMITTER_KEY: UNNAMED_EMITTER_ENTITY_ID})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == UNNAMED_EMITTER_ENTITY_ID


@pytest.mark.parametrize("consumer_flow", [MockDeviceTypeConsumerFlow])
@pytest.mark.parametrize(
    ("entry_data", "user_input"),
    [
        pytest.param(
            {EMITTER_KEY: EMITTER_ENTITY_ID},
            {CONF_DEVICE_TYPE: "tv", EMITTER_KEY: EMITTER_ENTITY_ID},
            id="same_emitter",
        ),
        pytest.param(
            {EMITTER_KEY: OTHER_ENTITY_ID, RECEIVER_KEY: RECEIVER_ENTITY_ID},
            {
                CONF_DEVICE_TYPE: "tv",
                EMITTER_KEY: EMITTER_ENTITY_ID,
                RECEIVER_KEY: RECEIVER_ENTITY_ID,
            },
            id="same_receiver",
        ),
    ],
)
@pytest.mark.parametrize(
    ("entry_device_type", "expected_type", "expected_reason"),
    [
        pytest.param(
            "tv", FlowResultType.ABORT, "already_configured", id="same_match_data"
        ),
        pytest.param("ac", FlowResultType.CREATE_ENTRY, None, id="other_match_data"),
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_infrared_entities_match(
    hass: HomeAssistant,
    entry_data: dict[str, str],
    user_input: dict[str, str],
    entry_device_type: str,
    expected_type: FlowResultType,
    expected_reason: str | None,
) -> None:
    """Test an infrared entity in use only aborts with the same match data."""
    MockConfigEntry(
        domain=TEST_DOMAIN, data={CONF_DEVICE_TYPE: entry_device_type, **entry_data}
    ).add_to_hass(hass)

    result = await _async_run_flow(hass, user_input)

    assert result["type"] is expected_type
    assert result.get("reason") == expected_reason


@pytest.mark.parametrize("consumer_flow", [MockDeviceTypeConsumerFlow])
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_reconfigure(hass: HomeAssistant) -> None:
    """Test reconfiguring keeps the data not in the form and drops cleared fields."""
    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={
            CONF_DEVICE_TYPE: "tv",
            EMITTER_KEY: EMITTER_ENTITY_ID,
            RECEIVER_KEY: RECEIVER_ENTITY_ID,
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert [str(key) for key in result["data_schema"].schema] == [
        EMITTER_KEY,
        RECEIVER_KEY,
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {EMITTER_KEY: EMITTER_ENTITY_ID}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_DEVICE_TYPE: "tv", EMITTER_KEY: EMITTER_ENTITY_ID}


@pytest.mark.parametrize("consumer_flow", [MockDeviceTypeConsumerFlow])
@pytest.mark.parametrize(
    ("other_entry_data", "user_input"),
    [
        pytest.param(
            {EMITTER_KEY: EMITTER_ENTITY_ID},
            {EMITTER_KEY: EMITTER_ENTITY_ID},
            id="same_emitter",
        ),
        pytest.param(
            {
                EMITTER_KEY: OTHER_ENTRY_EMITTER_ENTITY_ID,
                RECEIVER_KEY: RECEIVER_ENTITY_ID,
            },
            {EMITTER_KEY: EMITTER_ENTITY_ID, RECEIVER_KEY: RECEIVER_ENTITY_ID},
            id="same_receiver",
        ),
    ],
)
@pytest.mark.parametrize(
    ("other_device_type", "expected_reason", "expected_emitter"),
    [
        pytest.param("tv", "already_configured", OTHER_ENTITY_ID, id="same_match_data"),
        pytest.param(
            "ac", "reconfigure_successful", EMITTER_ENTITY_ID, id="other_match_data"
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
async def test_reconfigure_infrared_entities_match(
    hass: HomeAssistant,
    other_entry_data: dict[str, str],
    user_input: dict[str, str],
    other_device_type: str,
    expected_reason: str,
    expected_emitter: str,
) -> None:
    """Test reconfiguring only aborts when another entry has the same match data."""
    entry = MockConfigEntry(
        domain=TEST_DOMAIN, data={CONF_DEVICE_TYPE: "tv", EMITTER_KEY: OTHER_ENTITY_ID}
    )
    entry.add_to_hass(hass)
    MockConfigEntry(
        domain=TEST_DOMAIN,
        data={CONF_DEVICE_TYPE: other_device_type, **other_entry_data},
    ).add_to_hass(hass)

    result = await _async_run_reconfigure_flow(hass, entry, user_input)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    assert entry.data[EMITTER_KEY] == expected_emitter


@pytest.mark.parametrize("consumer_flow", [MockDeviceTypeConsumerFlow])
@pytest.mark.usefixtures("init_infrared")
async def test_reconfigure_abort_no_emitters(hass: HomeAssistant) -> None:
    """Test the reconfigure flow aborts when there are no infrared emitters."""
    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={CONF_DEVICE_TYPE: "tv", EMITTER_KEY: EMITTER_ENTITY_ID},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"
