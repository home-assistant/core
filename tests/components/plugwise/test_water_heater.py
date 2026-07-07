"""Tests for the Plugwise water_heater platform."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotSupported
from homeassistant.helpers import entity_registry as er
from syrupy.assertion import SnapshotAssertion

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

HA_PLUGWISE_SMILE_ASYNC_UPDATE = (
    "homeassistant.components.plugwise.coordinator.Smile.async_update"
)


@pytest.mark.parametrize("platforms", [(WATER_HEATER_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_adam_water_heater_snapshot(
    hass: HomeAssistant,
    mock_smile_adam_jip: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Adam water_heater snapshot with dhw_state off."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


async def test_adam_water_heater_setpoint_change(
    hass: HomeAssistant, mock_smile_adam_jip: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test Adam water_heater setpoint-change."""
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "water_heater.opentherm_dhw_temperature", ATTR_TEMPERATURE: 65},
        blocking=True,
    )
    assert mock_smile_adam_jip.set_number.call_count == 1
    mock_smile_adam_jip.set_number.assert_called_with(
        "e4684553153b44afbef2200885f379dc", "dhw_temperature", 65.0,
    )

    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_OPERATION_MODE,
            {ATTR_ENTITY_ID: "water_heater.opentherm_boiler_temperature", ATTR_OPERATION_MODE: "eco"},
            blocking=True,
        )
    assert mock_smile_adam_jip.set_dhw_mode.call_count == 0

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {ATTR_ENTITY_ID: "water_heater.opentherm_dhw_temperature", ATTR_OPERATION_MODE: "eco"},
        blocking=True,
    )
    assert mock_smile_adam_jip.set_dhw_mode.call_count == 1
    mock_smile_adam_jip.set_dhw_mode.assert_called_with(
        "dhw_mode", "e4684553153b44afbef2200885f379dc", 2, "eco"
    )


@pytest.mark.parametrize("chosen_env", ["anna_loria_cooling_active"], indirect=True)
@pytest.mark.parametrize("cooling_present", [False], indirect=True)
@pytest.mark.parametrize("platforms", [(WATER_HEATER_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_anna_water_heater_snapshot(
    hass: HomeAssistant,
    mock_smile_anna: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Anna water_heater snapshot with dhw_state on."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("chosen_env", ["anna_loria_cooling_active"], indirect=True)
@pytest.mark.parametrize("cooling_present", [False], indirect=True)
async def test_anna_water_heater_mode_change(
    hass: HomeAssistant,
    mock_smile_anna: MagicMock,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Anna water_heater dhw_mode changes."""
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {ATTR_ENTITY_ID: "water_heater.opentherm_dhw_temperature", ATTR_OPERATION_MODE: "off"},
        blocking=True,
    )
    assert mock_smile_anna.set_dhw_mode.call_count == 1
    mock_smile_anna.set_dhw_mode.assert_called_with(
        "dhw_mode", "bfb5ee0a88e14e5f97bfa725a760cc49", 5, "off"
    )

    data = mock_smile_anna.async_update.return_value
    data["bfb5ee0a88e14e5f97bfa725a760cc49"]["dhw_mode"] = "off"
    with patch(HA_PLUGWISE_SMILE_ASYNC_UPDATE, return_value=data):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_OPERATION_MODE,
            {ATTR_ENTITY_ID: "water_heater.opentherm_dhw_temperature", ATTR_OPERATION_MODE: "boost"},
            blocking=True,
        )
        assert mock_smile_anna.set_dhw_mode.call_count == 2
        mock_smile_anna.set_dhw_mode.assert_called_with(
            "dhw_mode", "bfb5ee0a88e14e5f97bfa725a760cc49", 5, "boost"
        )
