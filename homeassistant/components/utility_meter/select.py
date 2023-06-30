"""Support for tariff selection."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_METER,
    CONF_SOURCE_SENSOR,
    CONF_TARIFFS,
    DATA_UTILITY,
    TARIFF_ICON,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Utility Meter config entry."""
    name = config_entry.title
    tariffs: list[str] = config_entry.options[CONF_TARIFFS]

    unique_id = config_entry.entry_id

    registry = er.async_get(hass)
    source_entity = registry.async_get(config_entry.options[CONF_SOURCE_SENSOR])
    dev_reg = dr.async_get(hass)
    # Resolve source entity device
    if (
        (source_entity is not None)
        and (source_entity.device_id is not None)
        and (
            (
                device := dev_reg.async_get(
                    device_id=source_entity.device_id,
                )
            )
            is not None
        )
    ):
        device_info = DeviceInfo(
            identifiers=device.identifiers,
            connections=device.connections,
        )
    else:
        device_info = None

    tariff_select = TariffSelect(
        name,
        tariffs,
        unique_id,
        device_info=device_info,
    )
    async_add_entities([tariff_select])


async def async_setup_platform(
    hass: HomeAssistant,
    conf: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the utility meter select."""
    if discovery_info is None:
        _LOGGER.error(
            "This platform is not available to configure "
            "from 'select:' in configuration.yaml"
        )
        return

    meter: str = discovery_info[CONF_METER]
    conf_meter_unique_id: str | None = hass.data[DATA_UTILITY][meter].get(
        CONF_UNIQUE_ID
    )

    async_add_entities(
        [
            TariffSelect(
                meter,
                discovery_info[CONF_TARIFFS],
                conf_meter_unique_id,
            )
        ]
    )


class TariffSelect(SelectEntity, RestoreEntity):
    """Representation of a Tariff selector."""

    def __init__(
        self,
        name,
        tariffs,
        unique_id,
        device_info: DeviceInfo | None = None,
    ) -> None:
        """Initialize a tariff selector."""
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._current_tariff: str | None = None
        self._tariffs = tariffs
        self._attr_icon = TARIFF_ICON
        self._attr_should_poll = False

    @property
    def options(self) -> list[str]:
        """Return the available tariffs."""
        return self._tariffs

    @property
    def current_option(self) -> str | None:
        """Return current tariff."""
        return self._current_tariff

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if not state or state.state not in self._tariffs:
            self._current_tariff = self._tariffs[0]
        else:
            self._current_tariff = state.state

    async def async_select_option(self, option: str) -> None:
        """Select new tariff (option)."""
        self._current_tariff = option
        self.async_write_ha_state()
