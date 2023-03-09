"""Support for Xiaomi Mi Temp BLE environmental sensor."""
from __future__ import annotations

from homeassistant.components.sensor import PLATFORM_SCHEMA_BASE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

PLATFORM_SCHEMA = PLATFORM_SCHEMA_BASE


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MiTempBt sensor."""
    async_create_issue(
        hass,
        "mitemp_bt",
        "replaced",
        breaks_in_ha_version="2022.8.0",
        is_fixable=False,
        severity=IssueSeverity.ERROR,
        translation_key="replaced",
        learn_more_url="https://www.home-assistant.io/integrations/xiaomi_ble/",
    )
