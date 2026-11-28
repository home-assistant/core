"""Tests for the Solyx Energy Cloud select platform."""

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from solyx_energy_api.exceptions import SolyxEnergyAuthError, SolyxEnergyWriteError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.components.solyx_energy_cloud.const import (
    ATTRIBUTE_OPERATING_MODE,
    DATA_SETTLE_SECONDS,
    DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import NYMO_DEVICE_ID

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.SELECT]],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test all select entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_select_option(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_solyx_api_client: AsyncMock,
) -> None:
    """Selecting an operating mode writes it to the cloud, which the settle refresh confirms."""
    entity_id = entity_registry.async_get_entity_id(
        SELECT_DOMAIN, DOMAIN, f"{NYMO_DEVICE_ID}-operating_mode"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "direct"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, SelectServiceArgument.OPTION: "muted"},
        blocking=True,
    )
    mock_solyx_api_client.async_set_asset_attribute.assert_awaited_once_with(
        NYMO_DEVICE_ID, ATTRIBUTE_OPERATING_MODE, "MUTED"
    )
    # The new mode shows directly, without waiting for the settle refresh.
    assert hass.states.get(entity_id).state == "muted"

    # After the write settles, the actual data is retrieved through the API client.
    assets = mock_solyx_api_client.async_get_assets.return_value
    next(asset for asset in assets if asset["id"] == NYMO_DEVICE_ID)["attributes"][
        "operatingMode"
    ] = {"value": "MUTED"}
    freezer.tick(timedelta(seconds=DATA_SETTLE_SECONDS + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_solyx_api_client.async_get_assets.await_count == 2
    assert hass.states.get(entity_id).state == "muted"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(
            SolyxEnergyWriteError("write failed"),
            HomeAssistantError,
            id="write_error",
        ),
        pytest.param(
            SolyxEnergyAuthError("unauthorized"),
            ConfigEntryAuthFailed,
            id="auth_error",
        ),
    ],
)
async def test_select_option_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_solyx_api_client: AsyncMock,
    side_effect: Exception,
    expected_error: Callable[..., Exception],
) -> None:
    """A failed write surfaces as an error to the caller and keeps the previous state."""
    entity_id = entity_registry.async_get_entity_id(
        SELECT_DOMAIN, DOMAIN, f"{NYMO_DEVICE_ID}-operating_mode"
    )
    assert entity_id is not None

    mock_solyx_api_client.async_set_asset_attribute.side_effect = side_effect

    with pytest.raises(expected_error, match="API error|Auth error"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, SelectServiceArgument.OPTION: "muted"},
            blocking=True,
        )
    assert hass.states.get(entity_id).state == "direct"
