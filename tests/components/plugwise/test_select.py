"""Tests for the Plugwise Select integration."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("platforms", [(SELECT_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_adam_select_entities(
    hass: HomeAssistant,
    mock_smile_adam: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Adam select snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


async def test_adam_change_select_entity(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of select entities."""

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.woonkamer_thermostat_schedule",
            ATTR_OPTION: "Badkamer Schema",
        },
        blocking=True,
    )

    assert mock_smile_adam.set_select.call_count == 1
    mock_smile_adam.set_select.assert_called_with(
        "select_schedule",
        "c50f167537524366a5af7aa3942feb1e",
        "Badkamer Schema",
        "on",
    )


@pytest.mark.parametrize("chosen_env", ["m_adam_cooling"], indirect=True)
@pytest.mark.parametrize("cooling_present", [True], indirect=True)
@pytest.mark.parametrize("platforms", [(SELECT_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_adam_2_select_entities(
    hass: HomeAssistant,
    mock_smile_adam_heat_cool: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Adam with cooling select snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("chosen_env", ["m_adam_cooling"], indirect=True)
@pytest.mark.parametrize("cooling_present", [True], indirect=True)
async def test_adam_select_regulation_mode(
    hass: HomeAssistant,
    mock_smile_adam_heat_cool: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test changing the regulation_mode select.

    Also tests a change in climate _previous mode.
    """
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.adam_regulation_mode",
            ATTR_OPTION: "heating",
        },
        blocking=True,
    )
    assert mock_smile_adam_heat_cool.set_select.call_count == 1
    mock_smile_adam_heat_cool.set_select.assert_called_with(
        "select_regulation_mode",
        "bc93488efab249e5bc54fd7e175a6f91",
        "heating",
        "on",
    )


async def test_legacy_anna_select_entities(
    hass: HomeAssistant,
    mock_smile_legacy_anna: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test not creating a select-entity for a legacy Anna without a thermostat-schedule."""
    assert not hass.states.get("select.anna_thermostat_schedule")


@pytest.mark.parametrize("chosen_env", ["anna_heatpump_heating"], indirect=True)
@pytest.mark.parametrize("cooling_present", [True], indirect=True)
async def test_anna_select_unavailable_schedule_mode(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Fail-test an Anna thermostat_schedule select option."""

    with pytest.raises(ServiceValidationError, match="valid options"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.anna_thermostat_schedule",
                ATTR_OPTION: "Winter",
            },
            blocking=True,
        )
