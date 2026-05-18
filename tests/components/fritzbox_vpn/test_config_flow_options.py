"""Tests for options flow and confirm config flow steps."""

from unittest.mock import AsyncMock, patch

import pytest
from custom_components.fritzbox_vpn.config_flow import OptionsFlowHandler
from custom_components.fritzbox_vpn.const import (
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    OPTIONS_ACTION_CLEANUP,
    OPTIONS_ACTION_REPAIR_ENTITY_IDS,
    UNIQUE_ID_PREFIX,
)
from custom_components.fritzbox_vpn.flow_forms import CannotConnect
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_HOST, MOCK_PASSWORD, MOCK_USERNAME


@pytest.mark.asyncio
async def test_options_configure_updates_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Options configure step updates data, options, and reloads."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.fritzbox_vpn.config_flow.validate_input",
        new=AsyncMock(return_value={"title": mock_config_entry.title}),
    ), patch.object(
        hass.config_entries, "async_reload", new=AsyncMock()
    ) as reload_mock:
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.10",
                CONF_USERNAME: "new-user",
                CONF_PASSWORD: "new-pass",
                CONF_UPDATE_INTERVAL: 120,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    assert entry.data[CONF_HOST] == "192.168.1.10"
    assert entry.options[CONF_UPDATE_INTERVAL] == 120
    reload_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_options_init_shows_cleanup_action(
    hass: HomeAssistant, coordinator_with_data
) -> None:
    """Options init lists cleanup when orphaned entities exist."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}orphan_switch",
        config_entry=entry,
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"action": OPTIONS_ACTION_CLEANUP},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "cleanup_confirm"


@pytest.mark.asyncio
async def test_options_cleanup_confirm_removes_entities(
    hass: HomeAssistant, coordinator_with_data
) -> None:
    """Cleanup confirm removes orphaned registry entries."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}orphan_switch",
        config_entry=entry,
    )

    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"action": OPTIONS_ACTION_CLEANUP},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"confirm": True},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    remaining = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert all(
        "orphan" not in (e.unique_id or "")
        for e in remaining
    )


@pytest.mark.asyncio
async def test_user_autoconfig_from_fritz(hass: HomeAssistant) -> None:
    """User flow auto-creates entry when Fritz integration credentials work."""
    with patch(
        "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
        new=AsyncMock(
            return_value={
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            }
        ),
    ), patch(
        "custom_components.fritzbox_vpn.config_flow.validate_input",
        new=AsyncMock(return_value={"title": "Fritz!Box VPN"}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
async def test_options_init_shows_repair_action(hass: HomeAssistant) -> None:
    """Options init lists repair when suffixed entity IDs exist."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: MOCK_HOST})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}vpn1_switch",
        suggested_object_id="fritzbox_vpn_vpn1_switch_2",
        config_entry=entry,
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"action": OPTIONS_ACTION_REPAIR_ENTITY_IDS},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "repair_entity_ids_confirm"


@pytest.mark.asyncio
async def test_options_repair_entity_ids_confirm(hass: HomeAssistant) -> None:
    """Repair confirm runs repair and completes options flow."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: MOCK_HOST})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}vpn1_switch",
        suggested_object_id="fritzbox_vpn_vpn1_switch_2",
        config_entry=entry,
    )

    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"action": OPTIONS_ACTION_REPAIR_ENTITY_IDS},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"confirm": True},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
async def test_options_cleanup_confirm_error_key(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Cleanup confirm shows base error when orphans cannot be resolved."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.fritzbox_vpn.config_flow.get_orphaned_entity_entries",
        return_value=(None, "integration_not_loaded"),
    ):
        handler = OptionsFlowHandler(mock_config_entry)
        handler.hass = hass
        result = await handler.async_step_cleanup_confirm()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "integration_not_loaded"


@pytest.mark.asyncio
async def test_options_configure_validation_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Configure step shows base error when validation fails."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.fritzbox_vpn.config_flow.validate_input",
        new=AsyncMock(side_effect=CannotConnect),
    ):
        handler = OptionsFlowHandler(mock_config_entry)
        handler.hass = hass
        result = await handler.async_step_configure(
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
                CONF_UPDATE_INTERVAL: 60,
            }
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_options_abort_when_entry_removed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Options steps abort when config entry was removed."""
    mock_config_entry.add_to_hass(hass)
    handler = OptionsFlowHandler(mock_config_entry)
    handler.hass = hass
    with patch.object(
        hass.config_entries, "async_get_entry", return_value=None
    ):
        result = await handler.async_step_configure()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "config_entry_not_found"


@pytest.mark.asyncio
async def test_options_get_available_actions_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Options helper returns safe defaults when evaluation fails."""
    mock_config_entry.add_to_hass(hass)
    handler = OptionsFlowHandler(mock_config_entry)
    handler.hass = hass
    with patch(
        "custom_components.fritzbox_vpn.entity_registry.get_orphaned_entity_entries",
        side_effect=RuntimeError("boom"),
    ):
        has_cleanup, has_repair, count = handler._get_available_actions()
    assert has_cleanup is False
    assert has_repair is False
    assert count == 0
