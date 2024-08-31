"""Support for Huawei LTE selects."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
import logging

from huawei_lte_api.enums.net import LTEBandEnum, NetworkBandEnum, NetworkModeEnum

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED

from . import HuaweiLteBaseEntityWithDevice, Router
from .const import DOMAIN, KEY_NET_NET_MODE

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HuaweiSelectEntityDescription(SelectEntityDescription):
    """Class describing Huawei LTE select entities."""

    setter_fn: Callable[[str], None]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up from config entry."""
    router = hass.data[DOMAIN].routers[config_entry.entry_id]
    selects: list[Entity] = []

    desc = HuaweiSelectEntityDescription(
        key=KEY_NET_NET_MODE,
        entity_category=EntityCategory.CONFIG,
        name="Preferred network mode",
        translation_key="preferred_network_mode",
        options=[
            NetworkModeEnum.MODE_AUTO.value,
            NetworkModeEnum.MODE_4G_3G_AUTO.value,
            NetworkModeEnum.MODE_4G_2G_AUTO.value,
            NetworkModeEnum.MODE_4G_ONLY.value,
            NetworkModeEnum.MODE_3G_2G_AUTO.value,
            NetworkModeEnum.MODE_3G_ONLY.value,
            NetworkModeEnum.MODE_2G_ONLY.value,
        ],
        setter_fn=partial(
            router.client.net.set_net_mode,
            LTEBandEnum.ALL,
            NetworkBandEnum.ALL,
        ),
    )
    selects.append(
        HuaweiLteSelectEntity(
            router,
            entity_description=desc,
            key=desc.key,
            item="NetworkMode",
        )
    )

    async_add_entities(selects, True)


class HuaweiLteSelectEntity(HuaweiLteBaseEntityWithDevice, SelectEntity):
    """Huawei LTE select entity."""

    entity_description: HuaweiSelectEntityDescription
    _raw_state: str | None = None

    def __init__(
        self,
        router: Router,
        entity_description: HuaweiSelectEntityDescription,
        key: str,
        item: str,
    ) -> None:
        """Initialize."""
        super().__init__(router)
        self.entity_description = entity_description
        self.key = key
        self.item = item

        name = None
        if self.entity_description.name != UNDEFINED:
            name = self.entity_description.name
        self._attr_name = name or self.item

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self.entity_description.setter_fn(option)

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        return self._raw_state

    @property
    def _device_unique_id(self) -> str:
        return f"{self.key}.{self.item}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to needed data on add."""
        await super().async_added_to_hass()
        self.router.subscriptions[self.key].append(f"{SELECT_DOMAIN}/{self.item}")

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from needed data on remove."""
        await super().async_will_remove_from_hass()
        self.router.subscriptions[self.key].remove(f"{SELECT_DOMAIN}/{self.item}")

    async def async_update(self) -> None:
        """Update state."""
        try:
            value = self.router.data[self.key][self.item]
        except KeyError:
            _LOGGER.debug("%s[%s] not in data", self.key, self.item)
            self._available = False
            return
        self._available = True
        self._raw_state = str(value)
