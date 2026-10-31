"""Tests for the Anthropic integration."""

from datetime import UTC, datetime
from functools import partial
from typing import Literal, TypedDict
from unittest.mock import AsyncMock, patch

from anthropic import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
)
from anthropic.pagination import AsyncPage
from anthropic.types import ModelInfo
import attr
import httpx2
from httpx2 import URL, Request, Response
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import conversation
from homeassistant.components.anthropic.config_flow import AnthropicConfigFlow
from homeassistant.components.anthropic.const import (
    CONF_CHAT_MODEL,
    CONF_EFFORT,
    CONF_RECOMMENDED,
    CONF_THINKING_BUDGET,
    CONF_THINKING_TYPE,
    DOMAIN,
)
from homeassistant.config_entries import (
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigSubentryDataWithId,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import Context, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    intent,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import DeviceEntryDisabler
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.setup import async_setup_component

from . import create_content_block, model_list

MINOR_VERSION = AnthropicConfigFlow.MINOR_VERSION


class ConversationSubentryExpectation(TypedDict):
    """Expected registry state for a migrated conversation subentry."""

    conversation_entity_id: str
    device_disabled_by: DeviceEntryDisabler | None
    entity_disabled_by: RegistryEntryDisabler | None
    device: int


def _model_page(
    models: list[ModelInfo],
    *,
    lifecycle: list[Literal["active", "deprecated", "retired"]],
    timeout: float,
) -> AsyncPage[ModelInfo]:
    """Return models matching the requested lifecycle stages."""
    return AsyncPage(
        data=[model for model in models if model.lifecycle in lifecycle],
        has_more=False,
    )


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            APIConnectionError(request=None), "Connection error", id="connection_error"
        ),
        pytest.param(APITimeoutError(request=None), "Request timed out", id="timeout"),
        pytest.param(
            BadRequestError(
                message=(
                    "Your credit balance is too low to access"
                    " the Claude API. Please go to Plans &"
                    " Billing to upgrade or purchase credits."
                ),
                response=Response(
                    status_code=400,
                    request=Request(method="POST", url=URL()),
                ),
                body={"type": "error", "error": {"type": "invalid_request_error"}},
            ),
            "Your credit balance is too low to access the Claude API",
            id="insufficient_credit",
        ),
    ],
)
@pytest.mark.usefixtures("mock_config_entry")
async def test_init_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    side_effect: APIError,
    error: str,
) -> None:
    """Test initialization errors."""
    with patch(
        "anthropic.resources.models.AsyncModels.list",
        side_effect=side_effect,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert error in caplog.text


async def test_init_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test auth error during init errors."""
    with patch(
        "anthropic.resources.models.AsyncModels.list",
        side_effect=AuthenticationError(
            response=httpx2.Response(
                status_code=500, request=httpx2.Request(method="GET", url="test")
            ),
            body=None,
            message="",
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("lifecycle", "retires_at", "chat_model", "expected_issue"),
    [
        pytest.param("active", None, "claude-test-9", False, id="active"),
        pytest.param(
            "active",
            datetime(2025, 1, 1, tzinfo=UTC),
            "claude-test-9",
            False,
            id="active_with_past_retirement_date",
        ),
        pytest.param(
            "deprecated",
            datetime(2030, 1, 1, tzinfo=UTC),
            "claude-test-9",
            True,
            id="deprecated",
        ),
        pytest.param(
            "deprecated",
            datetime(2025, 1, 1, tzinfo=UTC),
            "claude-test-9",
            True,
            id="deprecated_with_overdue_retirement",
        ),
        pytest.param(
            "deprecated", None, "claude-test-9", True, id="no_retirement_date"
        ),
        pytest.param(
            "retired",
            datetime(2025, 1, 1, tzinfo=UTC),
            "claude-test-9",
            True,
            id="retired",
        ),
        pytest.param(
            "deprecated",
            None,
            "claude-test-9-20261001",
            True,
            id="dated_model",
        ),
        pytest.param(
            "deprecated", None, "claude-unknown-model", False, id="missing_model"
        ),
    ],
)
async def test_init_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
    issue_registry: ir.IssueRegistry,
    lifecycle: Literal["active", "deprecated", "retired"],
    retires_at: datetime | None,
    chat_model: str,
    expected_issue: bool,
) -> None:
    """Use API lifecycle rather than model names or retirement dates for repairs."""
    model_info = model_list[0].model_copy(
        update={
            "id": "claude-test-9",
            "lifecycle": lifecycle,
            "deprecated_at": datetime(2024, 1, 1, tzinfo=UTC),
            "retires_at": retires_at,
        }
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={"chat_model": chat_model},
    )
    mock_model_list.side_effect = partial(_model_page, [model_info])
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert (
        issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None
    ) is expected_issue


async def test_reconfigure_deprecated_model_repair(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Reconfiguring a subentry reloads its parent and creates a repair."""
    deprecated_model = model_list[0].model_copy(
        update={"id": "claude-test-deprecated", "lifecycle": "deprecated"}
    )
    mock_model_list.side_effect = partial(_model_page, [*model_list, deprecated_model])
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is None

    subentry = next(iter(mock_config_entry.subentries.values()))
    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_RECOMMENDED: False, CONF_CHAT_MODEL: deprecated_model.id},
    )
    assert result["step_id"] == "model"
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not coordinator
    assert subentry.data[CONF_CHAT_MODEL] == deprecated_model.id
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None


@pytest.mark.parametrize(
    "subentry_type",
    [
        pytest.param("conversation", id="conversation"),
        pytest.param("ai_task_data", id="ai_task"),
    ],
)
@pytest.mark.parametrize(
    "lifecycle",
    [
        pytest.param("deprecated", id="deprecated"),
        pytest.param("retired", id="retired"),
    ],
)
async def test_reconfigure_clears_model_repair(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
    issue_registry: ir.IssueRegistry,
    subentry_type: str,
    lifecycle: Literal["deprecated", "retired"],
) -> None:
    """Clear a repair discovered by the model picker after replacing that model."""
    configured_model = model_list[0].model_copy(update={"id": "claude-configured"})
    replacement_model = model_list[0].model_copy(update={"id": "claude-replacement"})
    subentry = next(
        subentry
        for subentry in mock_config_entry.subentries.values()
        if subentry.subentry_type == subentry_type
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry, subentry, data={CONF_CHAT_MODEL: configured_model.id}
    )
    mock_model_list.side_effect = partial(
        _model_page, [configured_model, replacement_model]
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is None

    mock_model_list.side_effect = partial(
        _model_page,
        [
            configured_model.model_copy(update={"lifecycle": lifecycle}),
            replacement_model,
        ],
    )
    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert result["step_id"] == "init"
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_RECOMMENDED: False, CONF_CHAT_MODEL: replacement_model.id},
    )
    assert result["step_id"] == "model"
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert subentry.data[CONF_CHAT_MODEL] == replacement_model.id
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is None


async def test_model_repair_retained_for_other_subentries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Retain the shared repair until all affected accounts and subentries are fixed."""
    deprecated_model = model_list[0].model_copy(
        update={"id": "claude-deprecated", "lifecycle": "deprecated"}
    )
    active_model = model_list[0].model_copy(update={"id": "claude-active"})
    for subentry in mock_config_entry.subentries.values():
        hass.config_entries.async_update_subentry(
            mock_config_entry, subentry, data={CONF_CHAT_MODEL: deprecated_model.id}
        )
    mock_model_list.side_effect = partial(_model_page, [deprecated_model, active_model])
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None

    disabled_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Disabled account",
        data={CONF_API_KEY: "disabled-api-key"},
        version=2,
        disabled_by=ConfigEntryDisabler.USER,
        subentries_data=[
            {
                "data": {CONF_CHAT_MODEL: deprecated_model.id},
                "subentry_type": "conversation",
                "title": "Disabled conversation",
                "unique_id": None,
            }
        ],
    )
    disabled_entry.add_to_hass(hass)
    assert disabled_entry.state is ConfigEntryState.NOT_LOADED

    healthy_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Other account",
        data={CONF_API_KEY: "other-api-key"},
        version=2,
        subentries_data=[
            {
                "data": {CONF_CHAT_MODEL: active_model.id},
                "subentry_type": "conversation",
                "title": "Other conversation",
                "unique_id": None,
            }
        ],
    )
    healthy_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(healthy_entry.entry_id)
    await hass.async_block_till_done()
    assert healthy_entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None

    mock_model_list.side_effect = partial(
        _model_page,
        [
            deprecated_model,
            active_model.model_copy(update={"display_name": "Updated active model"}),
        ],
    )
    healthy_subentry = next(iter(healthy_entry.subentries.values()))
    result = await healthy_entry.start_subentry_reconfigure_flow(
        hass, healthy_subentry.subentry_id
    )
    assert result["step_id"] == "init"
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_RECOMMENDED: False, CONF_CHAT_MODEL: active_model.id}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert healthy_entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None

    for subentry, expected_issue in zip(
        mock_config_entry.subentries.values(), (True, False), strict=True
    ):
        result = await mock_config_entry.start_subentry_reconfigure_flow(
            hass, subentry.subentry_id
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_RECOMMENDED: False, CONF_CHAT_MODEL: active_model.id},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert subentry.data[CONF_CHAT_MODEL] == active_model.id
        assert (
            issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None
        ) is expected_issue


@pytest.mark.usefixtures("mock_setup_entry")
async def test_downgrade_from_v3_to_v2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that migration from future versions is skipped."""
    # Create a v3 config entry
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        version=3,
        minor_version=0,
        subentries_data=[
            {
                "data": {
                    "recommended": True,
                    "llm_hass_api": ["assist"],
                    "prompt": "You are a helpful assistant",
                    "chat_model": "claude-haiku-4-5",
                },
                "subentry_id": "mock_id",
                "subentry_type": "conversation",
                "title": "Claude haiku",
                "unique_id": None,
            },
        ],
    )
    mock_config_entry.add_to_hass(hass)

    conversation_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id="mock_id",
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        config_subentry_id="mock_id",
        device_id=conversation_device.id,
        suggested_object_id="claude",
    )

    # Run migration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration was skipped and version was not updated
    assert mock_config_entry.version == 3
    assert mock_config_entry.minor_version == 0


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migration_from_v1_to_v2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 to version 2."""
    # Create a v1 config entry with conversation options and an entity
    OPTIONS = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "claude-haiku-4-5",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},
        options=OPTIONS,
        version=1,
        title="Claude",
    )
    mock_config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity = entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id="claude",
    )

    # Run migration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.version == 2
    assert mock_config_entry.minor_version == MINOR_VERSION
    assert mock_config_entry.data == {"api_key": "1234"}
    assert mock_config_entry.options == {}

    assert len(mock_config_entry.subentries) == 1

    subentry = next(iter(mock_config_entry.subentries.values()))
    assert subentry.unique_id is None
    assert subentry.title == "Claude"
    assert subentry.subentry_type == "conversation"
    assert subentry.data == OPTIONS

    migrated_entity = entity_registry.async_get(entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.config_entry_id == mock_config_entry.entry_id
    assert migrated_entity.config_subentry_id == subentry.subentry_id
    assert migrated_entity.unique_id == subentry.subentry_id

    # Check device migration
    assert not device_registry.async_get_devices(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert (
        migrated_device := device_registry.async_get_device_by_identifier(
            (DOMAIN, subentry.subentry_id), mock_config_entry.entry_id
        )
    )
    assert migrated_device.identifiers == {(DOMAIN, subentry.subentry_id)}
    assert migrated_device.id == device.id
    assert migrated_device.config_entry_id == mock_config_entry.entry_id
    assert migrated_device.config_subentry_id == subentry.subentry_id


@pytest.mark.parametrize(
    (
        "config_entry_disabled_by",
        "device_disabled_by",
        "entity_disabled_by",
        "merged_config_entry_disabled_by",
        "conversation_subentry_data",
        "main_config_entry",
    ),
    [
        pytest.param(
            [ConfigEntryDisabler.USER, None],
            [DeviceEntryDisabler.CONFIG_ENTRY, None],
            [RegistryEntryDisabler.CONFIG_ENTRY, None],
            None,
            [
                {
                    "conversation_entity_id": "conversation.claude_2",
                    "device_disabled_by": None,
                    "entity_disabled_by": None,
                    "device": 1,
                },
                {
                    "conversation_entity_id": "conversation.claude",
                    "device_disabled_by": DeviceEntryDisabler.USER,
                    "entity_disabled_by": RegistryEntryDisabler.DEVICE,
                    "device": 0,
                },
            ],
            1,
            id="first_entry_disabled",
        ),
        pytest.param(
            [None, ConfigEntryDisabler.USER],
            [None, DeviceEntryDisabler.CONFIG_ENTRY],
            [None, RegistryEntryDisabler.CONFIG_ENTRY],
            None,
            [
                {
                    "conversation_entity_id": "conversation.claude",
                    "device_disabled_by": None,
                    "entity_disabled_by": None,
                    "device": 0,
                },
                {
                    "conversation_entity_id": "conversation.claude_2",
                    "device_disabled_by": DeviceEntryDisabler.USER,
                    "entity_disabled_by": RegistryEntryDisabler.DEVICE,
                    "device": 1,
                },
            ],
            0,
            id="second_entry_disabled",
        ),
        pytest.param(
            [ConfigEntryDisabler.USER, ConfigEntryDisabler.USER],
            [DeviceEntryDisabler.CONFIG_ENTRY, DeviceEntryDisabler.CONFIG_ENTRY],
            [RegistryEntryDisabler.CONFIG_ENTRY, RegistryEntryDisabler.CONFIG_ENTRY],
            ConfigEntryDisabler.USER,
            [
                {
                    "conversation_entity_id": "conversation.claude",
                    "device_disabled_by": DeviceEntryDisabler.CONFIG_ENTRY,
                    "entity_disabled_by": RegistryEntryDisabler.CONFIG_ENTRY,
                    "device": 0,
                },
                {
                    "conversation_entity_id": "conversation.claude_2",
                    "device_disabled_by": DeviceEntryDisabler.CONFIG_ENTRY,
                    "entity_disabled_by": RegistryEntryDisabler.CONFIG_ENTRY,
                    "device": 1,
                },
            ],
            0,
            id="both_entries_disabled",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_migration_from_v1_disabled(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_disabled_by: list[ConfigEntryDisabler | None],
    device_disabled_by: list[DeviceEntryDisabler | None],
    entity_disabled_by: list[RegistryEntryDisabler | None],
    merged_config_entry_disabled_by: ConfigEntryDisabler | None,
    conversation_subentry_data: list[ConversationSubentryExpectation],
    main_config_entry: int,
) -> None:
    """Test migration where the config entries are disabled."""
    # Create a v1 config entry with conversation options and an entity
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "claude-haiku-4-5",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        options=options,
        version=1,
        title="Claude",
        disabled_by=config_entry_disabled_by[0],
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "1234"},
        options=options,
        version=1,
        title="Claude 2",
        disabled_by=config_entry_disabled_by[1],
    )
    mock_config_entry_2.add_to_hass(hass)
    mock_config_entries = [mock_config_entry, mock_config_entry_2]

    device_1 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
        disabled_by=device_disabled_by[0],
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device_1.id,
        suggested_object_id="claude",
        disabled_by=entity_disabled_by[0],
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
        disabled_by=device_disabled_by[1],
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="claude",
        disabled_by=entity_disabled_by[1],
    )

    devices = [device_1, device_2]

    # Run migration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.disabled_by is merged_config_entry_disabled_by
    assert entry.version == 2
    assert (
        entry.minor_version == 3
        if merged_config_entry_disabled_by is not None
        else MINOR_VERSION
    )
    assert not entry.options
    assert entry.title == "Claude conversation"
    assert len(entry.subentries) == 2
    conversation_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    ]
    assert len(conversation_subentries) == 2
    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "Claude" in subentry.title

    assert not device_registry.async_get_devices(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert not device_registry.async_get_devices(
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)}
    )

    for idx, subentry in enumerate(conversation_subentries):
        subentry_data = conversation_subentry_data[idx]
        entity = entity_registry.async_get(subentry_data["conversation_entity_id"])
        assert entity.unique_id == subentry.subentry_id
        assert entity.config_subentry_id == subentry.subentry_id
        assert entity.config_entry_id == entry.entry_id
        assert entity.disabled_by is subentry_data["entity_disabled_by"]

        assert (
            device := device_registry.async_get_device_by_identifier(
                (DOMAIN, subentry.subentry_id),
                mock_config_entries[main_config_entry].entry_id,
            )
        )
        assert device.identifiers == {(DOMAIN, subentry.subentry_id)}
        assert device.id == devices[subentry_data["device"]].id
        assert device.config_entry_id == mock_config_entries[main_config_entry].entry_id
        assert device.config_subentry_id == subentry.subentry_id
        assert device.disabled_by is subentry_data["device_disabled_by"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migration_from_v1_to_v2_with_multiple_keys(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 1 to version 2 with different API keys."""
    # Create two v1 config entries with different API keys
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "claude-haiku-4-5",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},
        options=options,
        version=1,
        title="Claude 1",
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "12345"},
        options=options,
        version=1,
        title="Claude 2",
    )
    mock_config_entry_2.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Anthropic",
        model="Claude 1",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id="claude_1",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="Anthropic",
        model="Claude 2",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="claude_2",
    )

    # Run migration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2

    for idx, entry in enumerate(entries):
        assert entry.version == 2
        assert entry.minor_version == MINOR_VERSION
        assert not entry.options
        assert len(entry.subentries) == 1
        subentry = list(entry.subentries.values())[0]
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert subentry.title == f"Claude {idx + 1}"

        dev = device_registry.async_get_device_by_identifier(
            (DOMAIN, list(entry.subentries.values())[0].subentry_id), entry.entry_id
        )
        assert dev is not None
        assert dev.config_entry_id == entry.entry_id
        assert dev.config_subentry_id == subentry.subentry_id


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migration_from_v1_to_v2_with_same_keys(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration v1 to v2 with same API keys.

    Consolidates entries.
    """
    # Create two v1 config entries with the same API key
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "claude-haiku-4-5",
    }
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},
        options=options,
        version=1,
        title="Claude",
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},  # Same API key
        options=options,
        version=1,
        title="Claude 2",
    )
    mock_config_entry_2.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        device_id=device.id,
        suggested_object_id="claude",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        identifiers={(DOMAIN, mock_config_entry_2.entry_id)},
        name=mock_config_entry_2.title,
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry_2.entry_id,
        config_entry=mock_config_entry_2,
        device_id=device_2.id,
        suggested_object_id="claude_2",
    )

    # Run migration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Should have only one entry left (consolidated)
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    entry = entries[0]
    assert entry.version == 2
    assert entry.minor_version == MINOR_VERSION
    assert not entry.options
    assert len(entry.subentries) == 2  # Two subentries from the two original entries

    # Check both subentries exist with correct data
    subentries = list(entry.subentries.values())
    titles = [sub.title for sub in subentries]
    assert "Claude" in titles
    assert "Claude 2" in titles

    for subentry in subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options

        # Check devices were migrated correctly
        dev = device_registry.async_get_device_by_identifier(
            (DOMAIN, subentry.subentry_id), mock_config_entry.entry_id
        )
        assert dev is not None
        assert dev.config_entry_id == mock_config_entry.entry_id
        assert dev.config_subentry_id == subentry.subentry_id


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migration_from_v2_1_to_v2_2(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration from version 2.1 to version 2.2."""
    # Create a v2.1 config entry with 2 subentries, devices and entities
    options = {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "claude-haiku-4-5",
    }
    subentries_data: list[ConfigSubentryDataWithId] = [
        {
            "data": options,
            "subentry_id": "mock_id_1",
            "subentry_type": "conversation",
            "title": "Claude",
            "unique_id": None,
        },
        {
            "data": options,
            "subentry_id": "mock_id_2",
            "subentry_type": "conversation",
            "title": "Claude 2",
            "unique_id": None,
        },
    ]
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "1234"},
        entry_id="mock_entry_id",
        version=2,
        minor_version=1,
        subentries_data=subentries_data,
        title="Claude",
    )
    mock_config_entry.add_to_hass(hass)

    device_1 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id="mock_id_1",
        identifiers={(DOMAIN, "mock_id_1")},
        name="Claude",
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        "mock_id_1",
        config_entry=mock_config_entry,
        config_subentry_id="mock_id_1",
        device_id=device_1.id,
        suggested_object_id="claude",
    )

    device_2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id="mock_id_2",
        identifiers={(DOMAIN, "mock_id_2")},
        name="Claude 2",
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        "mock_id_2",
        config_entry=mock_config_entry,
        config_subentry_id="mock_id_2",
        device_id=device_2.id,
        suggested_object_id="claude_2",
    )

    # Run migration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.version == 2
    assert entry.minor_version == MINOR_VERSION
    assert not entry.options
    assert entry.title == "Claude"
    assert len(entry.subentries) == 2
    conversation_subentries = [
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == "conversation"
    ]
    assert len(conversation_subentries) == 2
    for subentry in conversation_subentries:
        assert subentry.subentry_type == "conversation"
        assert subentry.data == options
        assert "Claude" in subentry.title

    subentry = conversation_subentries[0]

    entity = entity_registry.async_get("conversation.claude")
    assert entity.unique_id == subentry.subentry_id
    assert entity.config_subentry_id == subentry.subentry_id
    assert entity.config_entry_id == entry.entry_id

    assert not device_registry.async_get_devices(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert (
        device := device_registry.async_get_device_by_identifier(
            (DOMAIN, subentry.subentry_id), mock_config_entry.entry_id
        )
    )
    assert device.identifiers == {(DOMAIN, subentry.subentry_id)}
    assert device.id == device_1.id
    assert device.config_entry_id == mock_config_entry.entry_id
    assert device.config_subentry_id == subentry.subentry_id

    subentry = conversation_subentries[1]

    entity = entity_registry.async_get("conversation.claude_2")
    assert entity.unique_id == subentry.subentry_id
    assert entity.config_subentry_id == subentry.subentry_id
    assert entity.config_entry_id == entry.entry_id
    assert not device_registry.async_get_devices(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert (
        device := device_registry.async_get_device_by_identifier(
            (DOMAIN, subentry.subentry_id), mock_config_entry.entry_id
        )
    )
    assert device.identifiers == {(DOMAIN, subentry.subentry_id)}
    assert device.id == device_2.id
    assert device.config_entry_id == mock_config_entry.entry_id
    assert device.config_subentry_id == subentry.subentry_id


@pytest.mark.parametrize(
    (
        "config_entry_disabled_by",
        "device_disabled_by",
        "entity_disabled_by",
        "setup_result",
        "minor_version_after_migration",
        "config_entry_disabled_by_after_migration",
        "device_disabled_by_after_migration",
        "entity_disabled_by_after_migration",
    ),
    [
        # Config entry not disabled, update device and entity disabled by config entry
        pytest.param(
            None,
            DeviceEntryDisabler.CONFIG_ENTRY,
            RegistryEntryDisabler.CONFIG_ENTRY,
            True,
            MINOR_VERSION,
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
            id="enabled_entry_stale_flags",
        ),
        pytest.param(
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
            True,
            MINOR_VERSION,
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
            id="enabled_entry_device_disabled",
        ),
        pytest.param(
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.USER,
            True,
            MINOR_VERSION,
            None,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.USER,
            id="enabled_entry_entity_disabled",
        ),
        pytest.param(
            None,
            None,
            None,
            True,
            MINOR_VERSION,
            None,
            None,
            None,
            id="enabled_entry_no_disabled_flags",
        ),
        # Config entry disabled, migration does not run
        pytest.param(
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.CONFIG_ENTRY,
            RegistryEntryDisabler.CONFIG_ENTRY,
            False,
            2,
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.CONFIG_ENTRY,
            RegistryEntryDisabler.CONFIG_ENTRY,
            id="disabled_entry_config_entry_flags",
        ),
        pytest.param(
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
            False,
            2,
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.DEVICE,
            id="disabled_entry_device_disabled",
        ),
        pytest.param(
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.USER,
            False,
            2,
            ConfigEntryDisabler.USER,
            DeviceEntryDisabler.USER,
            RegistryEntryDisabler.USER,
            id="disabled_entry_entity_disabled",
        ),
        pytest.param(
            ConfigEntryDisabler.USER,
            None,
            None,
            False,
            2,
            ConfigEntryDisabler.USER,
            None,
            None,
            id="disabled_entry_no_disabled_flags",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_to_v2_3(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_disabled_by: ConfigEntryDisabler | None,
    device_disabled_by: DeviceEntryDisabler | None,
    entity_disabled_by: RegistryEntryDisabler | None,
    setup_result: bool,
    minor_version_after_migration: int,
    config_entry_disabled_by_after_migration: ConfigEntryDisabler | None,
    device_disabled_by_after_migration: DeviceEntryDisabler | None,
    entity_disabled_by_after_migration: RegistryEntryDisabler | None,
) -> None:
    """Test migration to version 2.3."""
    # Create a v2.2 config entry with conversation subentries
    conversation_subentry_id = "blabla"
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        disabled_by=config_entry_disabled_by,
        version=2,
        minor_version=2,
        subentries_data=[
            {
                "data": {
                    "recommended": True,
                    "llm_hass_api": ["assist"],
                    "prompt": "You are a helpful assistant",
                    "chat_model": "claude-haiku-4-5",
                },
                "subentry_id": conversation_subentry_id,
                "subentry_type": "conversation",
                "title": "Claude haiku",
                "unique_id": None,
            },
        ],
    )
    mock_config_entry.add_to_hass(hass)

    conversation_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id=conversation_subentry_id,
        identifiers={(DOMAIN, mock_config_entry.entry_id)},
        name=mock_config_entry.title,
        manufacturer="Anthropic",
        model="Claude",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    # A stale disabled_by flag can't be set through the registry API, which
    # validates it against the config entry's disabled state; write it
    # directly to simulate existing storage.
    conversation_device = attr.evolve(
        conversation_device, disabled_by=device_disabled_by
    )
    device_registry._devices[conversation_device.id] = conversation_device
    conversation_entity = entity_registry.async_get_or_create(
        "conversation",
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        config_subentry_id=conversation_subentry_id,
        device_id=conversation_device.id,
        suggested_object_id="claude",
    )
    conversation_entity = attr.evolve(
        conversation_entity, disabled_by=entity_disabled_by
    )
    entity_registry.entities[conversation_entity.entity_id] = conversation_entity

    # Verify initial state
    assert mock_config_entry.version == 2
    assert mock_config_entry.minor_version == 2
    assert len(mock_config_entry.subentries) == 1
    assert mock_config_entry.disabled_by == config_entry_disabled_by
    assert conversation_device.disabled_by == device_disabled_by
    assert conversation_entity.disabled_by == entity_disabled_by

    # Run setup to trigger migration
    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert result is setup_result
    await hass.async_block_till_done()

    # Verify migration completed
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]

    # Check version and subversion were updated
    assert entry.version == 2
    assert entry.minor_version == minor_version_after_migration

    # Check the disabled_by flag on config entry, device and entity are as expected
    conversation_device = device_registry.async_get(conversation_device.id)
    conversation_entity = entity_registry.async_get(conversation_entity.entity_id)
    assert mock_config_entry.disabled_by == config_entry_disabled_by_after_migration
    assert conversation_device.disabled_by == device_disabled_by_after_migration
    assert conversation_entity.disabled_by == entity_disabled_by_after_migration


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_to_v2_4(
    hass: HomeAssistant,
) -> None:
    """Test migration to version 2.4."""
    # Create a v2.3 config entry
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        version=2,
        minor_version=3,
        subentries_data=[
            {
                "data": {
                    "recommended": True,
                    "llm_hass_api": ["assist"],
                    "prompt": "You are a helpful assistant",
                    "chat_model": "claude-haiku-4-5",
                },
                "subentry_id": "mock_id_1",
                "subentry_type": "conversation",
                "title": "Claude haiku default",
                "unique_id": None,
            },
            {
                "data": {
                    "recommended": False,
                    "llm_hass_api": ["assist"],
                    "prompt": "You are a helpful assistant",
                    "chat_model": "claude-haiku-4-5",
                    "temperature": 0.5,
                },
                "subentry_id": "mock_id_2",
                "subentry_type": "conversation",
                "title": "Claude haiku non-default",
                "unique_id": None,
            },
        ],
    )
    mock_config_entry.add_to_hass(hass)

    # Run migration
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that minor version was updated
    assert mock_config_entry.version == 2
    assert mock_config_entry.minor_version == MINOR_VERSION

    # Verify data was not changed for the first subentry
    assert mock_config_entry.subentries["mock_id_1"].data == {
        "recommended": True,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "claude-haiku-4-5",
    }

    # Verify that temperature was removed from the second subentry
    assert mock_config_entry.subentries["mock_id_2"].data == {
        "recommended": False,
        "llm_hass_api": ["assist"],
        "prompt": "You are a helpful assistant",
        "chat_model": "claude-haiku-4-5",
    }


@pytest.mark.parametrize(
    "subentry_type",
    [
        pytest.param("conversation", id="conversation"),
        pytest.param("ai_task_data", id="ai_task"),
    ],
)
@pytest.mark.parametrize(
    ("subentry_options", "expected_options"),
    [
        pytest.param({}, {}, id="defaults"),
        pytest.param(
            {"thinking_effort": "high", CONF_THINKING_BUDGET: 0},
            {CONF_EFFORT: "high", CONF_THINKING_BUDGET: 0},
            id="effort_with_disabled_manual_thinking",
        ),
        pytest.param(
            {CONF_RECOMMENDED: True, "thinking_effort": "none"},
            {
                CONF_RECOMMENDED: True,
                CONF_THINKING_TYPE: "disabled",
            },
            id="recommended_with_disabled_thinking",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_to_v2_5(
    hass: HomeAssistant,
    subentry_type: str,
    subentry_options: dict[str, str | int | bool],
    expected_options: dict[str, str | int | bool],
) -> None:
    """Migrate effort independently from the selected thinking type."""
    common_options = {
        CONF_CHAT_MODEL: "claude-test-model",
        CONF_RECOMMENDED: False,
        "max_tokens": 4096,
        "prompt": "You are a helpful assistant",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        version=2,
        minor_version=4,
        subentries_data=[
            {
                "data": common_options | subentry_options,
                "subentry_id": "mock_id",
                "subentry_type": subentry_type,
                "title": "Claude",
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.minor_version == MINOR_VERSION
    assert entry.subentries["mock_id"].data == common_options | expected_options


@pytest.mark.parametrize(
    ("model", "legacy_options", "expected_options", "expected_effort"),
    [
        pytest.param(
            "claude-haiku-4-5",
            {CONF_THINKING_BUDGET: 0},
            {CONF_THINKING_BUDGET: 0},
            None,
            id="manual_without_effort",
        ),
        pytest.param(
            "claude-opus-4-5",
            {CONF_THINKING_BUDGET: 0},
            {CONF_THINKING_BUDGET: 0},
            {"effort": "low"},
            id="manual_with_effort",
        ),
        pytest.param(
            "claude-haiku-5-5",
            {"thinking_effort": "none"},
            {CONF_THINKING_TYPE: "disabled"},
            {"effort": "low"},
            id="adaptive",
        ),
    ],
)
@pytest.mark.usefixtures("mock_model_list")
async def test_migrate_disabled_thinking_request(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
    model: str,
    legacy_options: dict[str, str | int],
    expected_options: dict[str, str | int],
    expected_effort: dict[str, str] | None,
) -> None:
    """Preserve disabled thinking through migration, setup, and the first request."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        version=2,
        minor_version=4,
        subentries_data=[
            {
                "data": {CONF_CHAT_MODEL: model} | legacy_options,
                "subentry_id": "mock_id",
                "subentry_type": "conversation",
                "title": "Claude conversation",
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        entry.subentries["mock_id"].data == {CONF_CHAT_MODEL: model} | expected_options
    )
    mock_create_stream.return_value = [create_content_block(0, ["Hello"])]

    result = await conversation.async_converse(
        hass,
        "hello",
        None,
        Context(),
        agent_id="conversation.claude_conversation",
    )

    assert entry.minor_version == MINOR_VERSION
    assert (
        entry.subentries["mock_id"].data == {CONF_CHAT_MODEL: model} | expected_options
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    request = mock_create_stream.call_args.kwargs
    assert request["thinking"] == {"type": "disabled"}
    assert request.get("output_config") == expected_effort
