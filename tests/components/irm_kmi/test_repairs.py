"""Tests for the repair flow of IRM KMI integration."""

import logging
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.irm_kmi import DOMAIN, IrmKmiCoordinator
from homeassistant.components.irm_kmi.const import (
    REPAIR_OPT_DELETE,
    REPAIR_OPT_MOVE,
    REPAIR_SOLUTION,
)
from homeassistant.components.irm_kmi.repairs import (
    OutOfBeneluxRepairFlow,
    async_create_fix_flow,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def get_repair_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> OutOfBeneluxRepairFlow:
    """Return a repair flow due a zone being outside of Benelux."""
    hass.states.async_set(
        "zone.home",
        0,
        {"latitude": 50.738681639, "longitude": 4.054077148},
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_config_entry.runtime_data = AsyncMock()
    mock_config_entry.runtime_data.get_city = MagicMock(
        return_value="Outside the Benelux (Brussels)"
    )

    coordinator = IrmKmiCoordinator(hass, mock_config_entry)

    await coordinator.async_refresh()
    registry = ir.async_get(hass)
    issue = registry.async_get_issue(DOMAIN, "zone_moved")
    repair_flow = await async_create_fix_flow(hass, issue.issue_id, issue.data)
    repair_flow.hass = hass
    return repair_flow


async def test_repair_triggers_when_out_of_benelux(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a zone out of Benelux triggers a repair."""
    hass.states.async_set(
        "zone.home",
        0,
        {"latitude": 50.738681639, "longitude": 4.054077148},
    )

    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = AsyncMock()
    mock_config_entry.runtime_data.get_city = MagicMock(
        return_value="Outside the Benelux (Brussels)"
    )

    coordinator = IrmKmiCoordinator(hass, mock_config_entry)

    await coordinator.async_refresh()

    registry = ir.async_get(hass)

    issue = registry.async_get_issue(DOMAIN, "zone_moved")

    assert issue is not None
    assert issue.data == {
        "config_entry_id": mock_config_entry.entry_id,
        "zone": "zone.home",
    }
    assert issue.translation_key == "zone_moved"
    assert issue.is_fixable
    assert issue.translation_placeholders == {"zone": "zone.home"}


async def test_repair_flow(
    hass: HomeAssistant,
    mock_irm_kmi_api_repair_in_benelux: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the repair is resolved once the user moved the zone."""
    repair_flow = await get_repair_flow(hass, mock_config_entry)
    result = await repair_flow.async_step_init()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    assert result["description_placeholders"] == {"zone": "zone.home"}

    user_input = {REPAIR_SOLUTION: REPAIR_OPT_MOVE}

    result = await repair_flow.async_step_confirm(user_input)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {}


async def test_repair_flow_invalid_choice(
    hass: HomeAssistant,
    mock_irm_kmi_api_repair_in_benelux: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test repair flow error when we get invalid solution option."""
    repair_flow = await get_repair_flow(hass, mock_config_entry)
    result = await repair_flow.async_step_init()

    assert result["type"] == FlowResultType.FORM
    user_input = {REPAIR_SOLUTION: "whut?"}

    result = await repair_flow.async_step_confirm(user_input)

    assert result["type"] == FlowResultType.FORM
    assert REPAIR_SOLUTION in result["errors"]
    assert result["errors"][REPAIR_SOLUTION] == "invalid_choice"


async def test_repair_flow_api_error(
    hass: HomeAssistant,
    mock_get_forecast_api_error_repair: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the repair flow when the API returns an error."""
    repair_flow = await get_repair_flow(hass, mock_config_entry)
    result = await repair_flow.async_step_init()

    assert result["type"] == FlowResultType.FORM
    user_input = {REPAIR_SOLUTION: REPAIR_OPT_MOVE}

    result = await repair_flow.async_step_confirm(user_input)

    assert result["type"] == FlowResultType.FORM
    assert REPAIR_SOLUTION in result["errors"]
    assert result["errors"][REPAIR_SOLUTION] == "api_error"


async def test_repair_flow_out_of_benelux(
    hass: HomeAssistant,
    mock_irm_kmi_api_repair_out_of_benelux: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test repair flow when the user pretend to move the zone but did not actually do it."""
    repair_flow = await get_repair_flow(hass, mock_config_entry)
    result = await repair_flow.async_step_init()

    assert result["type"] == FlowResultType.FORM
    user_input = {REPAIR_SOLUTION: REPAIR_OPT_MOVE}

    result = await repair_flow.async_step_confirm(user_input)

    assert result["type"] == FlowResultType.FORM
    assert REPAIR_SOLUTION in result["errors"]
    assert result["errors"][REPAIR_SOLUTION] == "out_of_benelux"


async def test_repair_flow_delete_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test repair flow when the user opts to delete the configuration that is outside the Benelux."""
    repair_flow = await get_repair_flow(hass, mock_config_entry)
    result = await repair_flow.async_step_init()

    assert result["type"] == FlowResultType.FORM
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert (
        hass.config_entries.async_entries(DOMAIN)[0].entry_id
        == mock_config_entry.entry_id
    )

    user_input = {REPAIR_SOLUTION: REPAIR_OPT_DELETE}
    result = await repair_flow.async_step_confirm(user_input)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"] == {}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
