"""Test the Home Assistant fyta sensor module."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from fyta_cli.fyta_exceptions import FytaConnectionError, FytaPlantError
from fyta_cli.fyta_models import Plant
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.fyta.const import DOMAIN as FYTA_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
)
from tests.typing import ClientSessionGenerator


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_fyta_connector: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""

    await setup_platform(hass, mock_config_entry, [Platform.IMAGE])

    assert len(hass.states.async_all("image")) == 2


@pytest.mark.parametrize(
    "exception",
    [
        FytaConnectionError,
        FytaPlantError,
    ],
)
async def test_connection_error(
    hass: HomeAssistant,
    exception: Exception,
    mock_fyta_connector: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test connection error."""
    await setup_platform(hass, mock_config_entry, [Platform.IMAGE])

    mock_fyta_connector.update_all_plants.side_effect = exception

    freezer.tick(delta=timedelta(hours=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("image.gummibaum_picture").state == STATE_UNAVAILABLE


async def test_add_remove_entities(
    hass: HomeAssistant,
    mock_fyta_connector: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test if entities are added and old are removed."""
    await setup_platform(hass, mock_config_entry, [Platform.IMAGE])

    assert hass.states.get("image.gummibaum_picture") is not None

    plants: dict[int, Plant] = {
        0: Plant.from_dict(load_json_object_fixture("plant_status1.json", FYTA_DOMAIN)),
        2: Plant.from_dict(load_json_object_fixture("plant_status3.json", FYTA_DOMAIN)),
    }
    mock_fyta_connector.update_all_plants.return_value = plants
    mock_fyta_connector.plant_list = {
        0: "Kautschukbaum",
        2: "Tomatenpflanze",
    }

    freezer.tick(delta=timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("image.kakaobaum_picture") is None
    assert hass.states.get("image.tomatenpflanze_picture") is not None
