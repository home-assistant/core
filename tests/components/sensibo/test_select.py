"""The test for the sensibo select platform."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from pysensibo.model import SensiboData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.SELECT]],
)
async def test_select(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    mock_client: MagicMock,
    get_data: tuple[SensiboData, dict[str, Any]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo select."""

    await snapshot_platform(hass, entity_registry, snapshot, load_int.entry_id)

    monkeypatch.setattr(
        get_data[0].parsed["ABC999111"], "horizontal_swing_mode", "fixedleft"
    )

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("select.hallway_horizontal_swing")
    assert state.state == "fixedleft"


async def test_select_set_option(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    mock_client: MagicMock,
    get_data: tuple[SensiboData, dict[str, Any]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo select service."""

    monkeypatch.setattr(
        get_data[0].parsed["ABC999111"],
        "active_features",
        [
            "timestamp",
            "on",
            "mode",
            "targetTemperature",
            "light",
        ],
    )

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("select.hallway_horizontal_swing")
    assert state.state == "stopped"

    mock_client.async_set_ac_state_property = AsyncMock(
        return_value={"result": {"status": "failed"}}
    )

    with pytest.raises(
        HomeAssistantError,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_OPTION: "fixedleft"},
            blocking=True,
        )

    state = hass.states.get("select.hallway_horizontal_swing")
    assert state.state == "stopped"

    monkeypatch.setattr(
        get_data[0].parsed["ABC999111"],
        "active_features",
        [
            "timestamp",
            "on",
            "mode",
            "targetTemperature",
            "horizontalSwing",
            "light",
        ],
    )

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_client.async_set_ac_state_property = AsyncMock(
        return_value={"result": {"status": "Failed", "failureReason": "No connection"}}
    )

    with pytest.raises(
        HomeAssistantError,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_OPTION: "fixedleft"},
            blocking=True,
        )

    state = hass.states.get("select.hallway_horizontal_swing")
    assert state.state == "stopped"

    mock_client.async_set_ac_state_property = AsyncMock(
        return_value={"result": {"status": "Success"}}
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_OPTION: "fixedleft"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.hallway_horizontal_swing")
    assert state.state == "fixedleft"
