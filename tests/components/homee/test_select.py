"""Test homee selects."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_FIRST,
    SERVICE_SELECT_LAST,
    SERVICE_SELECT_NEXT,
    SERVICE_SELECT_OPTION,
    SERVICE_SELECT_PREVIOUS,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def setup_select(
    hass: HomeAssistant, mock_homee: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Setups the integration for select tests."""
    mock_homee.nodes = [build_mock_node("selects.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)


@pytest.mark.parametrize(
    ("service", "extra_options", "expected"),
    [
        (SERVICE_SELECT_FIRST, {}, 0),
        (SERVICE_SELECT_LAST, {}, 2),
        (SERVICE_SELECT_NEXT, {}, 2),
        (SERVICE_SELECT_PREVIOUS, {}, 0),
        (
            SERVICE_SELECT_OPTION,
            {
                "option": "level2",
            },
            2,
        ),
    ],
)
async def test_select_services(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    extra_options: dict[str, str],
    expected: int,
) -> None:
    """Test the select services."""
    await setup_select(hass, mock_homee, mock_config_entry)

    OPTIONS = {ATTR_ENTITY_ID: "select.test_select_repeater_mode"}
    OPTIONS.update(extra_options)

    await hass.services.async_call(
        SELECT_DOMAIN,
        service,
        OPTIONS,
        blocking=True,
    )

    mock_homee.set_value.assert_called_once_with(1, 1, expected)


async def test_select_option_service_error(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the select_option service called with invalid option."""
    await setup_select(hass, mock_homee, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.test_select_repeater_mode",
                "option": "invalid",
            },
            blocking=True,
        )


async def test_select_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the select entity snapshot."""
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.SELECT]):
        await setup_select(hass, mock_homee, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
