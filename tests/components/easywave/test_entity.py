"""Tests for Easywave entity helpers."""

from typing import override

from homeassistant.components.easywave.entity import EasywaveChildEntity
from homeassistant.core import HomeAssistant
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
        identifiers={("easywave", "child")},
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
