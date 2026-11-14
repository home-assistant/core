"""Common fixtures for the Monoprice tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.monoprice.const import CONF_NOT_FIRST_RUN, DOMAIN
from homeassistant.components.monoprice.coordinator import ZONE_IDS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_CONFIG, MockMonoprice


@pytest.fixture
def client() -> Generator[MagicMock]:
    """Use a stateful amplifier mock with recorded calls."""
    device = MagicMock(wraps=MockMonoprice())
    with patch("homeassistant.components.monoprice.get_monoprice", return_value=device):
        yield device


@pytest.fixture
async def entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> MockConfigEntry:
    """Set up an existing amplifier with two enabled zones."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={**MOCK_CONFIG, CONF_NOT_FIRST_RUN: True}
    )
    config_entry.add_to_hass(hass)
    for zone in ZONE_IDS:
        entity_registry.async_get_or_create(
            "media_player",
            DOMAIN,
            f"{config_entry.entry_id}_{zone}",
            suggested_object_id=f"zone_{zone}",
            config_entry=config_entry,
            disabled_by=None if zone in (11, 12) else er.RegistryEntryDisabler.USER,
        )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
