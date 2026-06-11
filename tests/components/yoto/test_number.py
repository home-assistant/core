"""Tests for the Yoto number platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from yoto_api import YotoError

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import PLAYER_ID

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.usefixtures("setup_credentials")


async def _setup(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the integration with only the number platform."""
    with patch("homeassistant.components.yoto.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)


@pytest.mark.usefixtures("mock_yoto_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every Yoto number entity."""
    await _setup(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "value", "expected_fields"),
    [
        pytest.param(
            "number.nursery_yoto_day_maximum_volume",
            70,
            {"day_max_volume_limit": 70},
            id="day-max-volume",
        ),
        pytest.param(
            "number.nursery_yoto_night_maximum_volume",
            30,
            {"night_max_volume_limit": 30},
            id="night-max-volume",
        ),
        pytest.param(
            "number.nursery_yoto_day_display_brightness",
            90,
            {"day_display_brightness": 90},
            id="day-display-brightness",
        ),
        pytest.param(
            "number.nursery_yoto_night_display_brightness",
            20,
            {"night_display_brightness": 20},
            id="night-display-brightness",
        ),
        pytest.param(
            "number.nursery_yoto_dimmed_display_brightness",
            5,
            {"display_dim_brightness": 5},
            id="dim-brightness",
        ),
        pytest.param(
            "number.nursery_yoto_auto_shutdown_delay",
            1800,
            {"shutdown_timeout": 1800},
            id="shutdown-timeout",
        ),
        pytest.param(
            "number.nursery_yoto_display_dim_delay",
            60,
            {"display_dim_timeout": 60},
            id="display-dim-timeout",
        ),
    ],
)
async def test_set_value(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    value: int,
    expected_fields: dict[str, int],
) -> None:
    """Setting a number writes the matching player config field."""
    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    mock_yoto_client.set_player_config.assert_awaited_once_with(
        PLAYER_ID, **expected_fields
    )
    mock_yoto_client.update_player_info.assert_awaited_once_with(PLAYER_ID)


async def test_set_value_failure(
    hass: HomeAssistant,
    mock_yoto_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failed config write raises a Home Assistant error."""
    await _setup(hass, mock_config_entry)
    mock_yoto_client.set_player_config.side_effect = YotoError("MQTT timeout")

    with pytest.raises(
        HomeAssistantError, match="Failed to update Yoto player settings"
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: "number.nursery_yoto_day_maximum_volume", ATTR_VALUE: 50},
            blocking=True,
        )
