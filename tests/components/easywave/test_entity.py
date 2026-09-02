"""Tests for Easywave entity helpers."""

from typing import override

from homeassistant.components.easywave.const import DOMAIN
from homeassistant.components.easywave.entity import EasywaveChildEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .conftest import async_setup_easywave_entry

from tests.common import MockConfigEntry


class _EntityWithoutDeviceInfo(EasywaveChildEntity):
    """Entity stub that reports no device info."""

    _entry: MockConfigEntry

    @override
    @property
    def device_info(self) -> None:
        return None


class _ChildEntity(EasywaveChildEntity):
    """Entity stub with device info for gateway linking."""

    _entry: MockConfigEntry

    _attr_device_info = DeviceInfo(
        identifiers={(DOMAIN, "child")},
        name="Child",
    )


async def test_link_device_to_gateway_skips_entities_without_device_info(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Entities without device info are left unchanged when linking to the gateway."""
    await async_setup_easywave_entry(hass, mock_config_entry)
    entity = _EntityWithoutDeviceInfo()
    entity._entry = mock_config_entry
    entity.hass = hass

    entity._link_device_to_gateway()

    assert entity.device_info is None


async def test_link_device_to_gateway_sets_via_device_id(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Child entities are linked to the gateway device once it exists."""
    await async_setup_easywave_entry(hass, mock_config_entry)
    entity = _ChildEntity()
    entity._entry = mock_config_entry
    entity.hass = hass

    entity._link_device_to_gateway()

    assert entity.device_info is not None
    assert entity.device_info.get("via_device_id") is not None
    assert "via_device" not in entity.device_info


async def test_link_device_to_gateway_updates_device_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Parent linking persists via_device_id on the already-created registry device."""
    await async_setup_easywave_entry(hass, mock_config_entry)
    child = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "child")},
        name="Child",
    )
    assert child.via_device_id is None

    entity = _ChildEntity()
    entity._entry = mock_config_entry
    entity.hass = hass
    entity.device_entry = child

    entity._link_device_to_gateway()

    updated = device_registry.async_get(child.id)
    assert updated is not None
    assert updated.via_device_id is not None
    assert entity.device_entry is not None
    assert entity.device_entry.via_device_id == updated.via_device_id
