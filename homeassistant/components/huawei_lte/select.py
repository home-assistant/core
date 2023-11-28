"""Support for Huawei LTE selects."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
import logging

from huawei_lte_api.enums.net import LTEBandEnum, NetworkBandEnum

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

from . import HuaweiLteBaseEntityWithDevice
from .const import DOMAIN, KEY_NET_NET_MODE, NETWORKMODE_TO_STRING

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up from config entry."""
    router = hass.data[DOMAIN].routers[config_entry.entry_id]
    selects: list[Entity] = []

    desc = SelectEntityDescription(
        key="network_mode", name="Preferred mode", entity_category=EntityCategory.CONFIG
    )
    selects.append(
        HuaweiLteBaseSelect(
            router,
            entity_description=desc,
            key=KEY_NET_NET_MODE,
            item="NetworkMode",
            choices=NETWORKMODE_TO_STRING,
            setter_fn=partial(
                router.client.net.set_net_mode,
                LTEBandEnum.ALL,
                NetworkBandEnum.ALL,
            ),
        )
    )

    async_add_entities(selects, True)


@dataclass
class HuaweiLteBaseSelect(HuaweiLteBaseEntityWithDevice, SelectEntity):
    """Huawei LTE select base class."""

    entity_description: SelectEntityDescription
    key: str
    item: str
    choices: dict[str, str]
    setter_fn: Callable[[str], None]

    _raw_state: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Initialize remaining attributes."""
        name = None
        if self.entity_description.name != UNDEFINED:
            name = self.entity_description.name
        self._attr_name = name or self.item

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        choices_reverse = {v: k for k, v in self.choices.items()}
        self.setter_fn(choices_reverse[option])

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        state_str = None
        if self._raw_state is not None:
            state_str = self.choices.get(self._raw_state)
        if state_str is None:
            _LOGGER.warning("Unknown state: %s", self._raw_state)

        return state_str

    @property
    def options(self) -> list[str]:
        """Return available options."""
        return list(self.choices.values())

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
