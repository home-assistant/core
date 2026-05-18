"""Test Schlage select."""

from collections.abc import Awaitable, Callable
from unittest.mock import Mock, patch

from pyschlage.lock import AUTO_LOCK_TIMES

from homeassistant.components.schlage.const import DOMAIN
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import LOCALE_EN, async_get_translations

from . import MockSchlageConfigEntry

from tests.common import SnapshotAssertion, snapshot_platform


async def test_select_attributes(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockSchlageConfigEntry]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test select attributes."""
    with patch("homeassistant.components.schlage.PLATFORMS", [Platform.SELECT]):
        config_entry = await mock_add_config_entry()
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_select(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_add_config_entry: Callable[[], Awaitable[MockSchlageConfigEntry]],
) -> None:
    """Test the auto-lock time select entity."""
    with patch("homeassistant.components.schlage.PLATFORMS", [Platform.SELECT]):
        await mock_add_config_entry()

        select = hass.states.get("select.vault_door_auto_lock_time")
        assert select is not None
        assert select.state == "15"

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: select.entity_id, ATTR_OPTION: "30"},
            blocking=True,
        )
        mock_lock.set_auto_lock_time.assert_called_once_with(30)


async def test_auto_lock_time_translations(hass: HomeAssistant) -> None:
    """Test all auto_lock_time select options are translated."""
    prefix = f"component.{DOMAIN}.entity.{Platform.SELECT.value}.auto_lock_time.state."
    translations = await async_get_translations(hass, LOCALE_EN, "entity", [DOMAIN])
    got_translation_states = {k for k in translations if k.startswith(prefix)}
    want_translation_states = {f"{prefix}{t}" for t in AUTO_LOCK_TIMES}
    assert want_translation_states == got_translation_states
