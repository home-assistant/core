"""Module for SIA Binary Sensors."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pysiaalarm import SIAEvent

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    LOGGER,
    SIA_HUB_ZONE,
    SIA_UNIQUE_ID_FORMAT_BINARY,
)
from .sia_entity_base import SIABaseEntity
from .utils import SIARequiredKeysMixin


@dataclass
class SIABinarySensorEntityDescription(
    BinarySensorEntityDescription,
    SIARequiredKeysMixin,
):
    """Describes SIA sensor entity."""


entity_description_power = SIABinarySensorEntityDescription(
    key="power",
    device_class=BinarySensorDeviceClass.POWER,
    entity_category="diagnostic",
    code_consequences={
        "AT": False,
        "AR": True,
    },
    always_reset_availability=True,
)

entity_description_smoke = SIABinarySensorEntityDescription(
    key="smoke",
    device_class=BinarySensorDeviceClass.SMOKE,
    code_consequences={
        "GA": True,
        "GH": False,
        "FA": True,
        "FH": False,
        "KA": True,
        "KH": False,
    },
    always_reset_availability=True,
)

entity_description_moisture = SIABinarySensorEntityDescription(
    key="moisture",
    device_class=BinarySensorDeviceClass.MOISTURE,
    code_consequences={
        "WA": True,
        "WH": False,
    },
    always_reset_availability=True,
)


def generate_binary_sensors(entry) -> Iterable[SIABinarySensor]:
    """Generate binary sensors.

    For each Account there is one power sensor with zone == 0.
    For each Zone in each Account there is one smoke and one moisture sensor.
    """
    for account_data in entry.data[CONF_ACCOUNTS]:
        yield SIABinarySensor(
            port=entry.data[CONF_PORT],
            account=account_data[CONF_ACCOUNT],
            zone=SIA_HUB_ZONE,
            ping_interval=account_data[CONF_PING_INTERVAL],
            entry_id=entry.entry_id,
            entity_description=entity_description_power,
        )
        zones = entry.options[CONF_ACCOUNTS][account_data[CONF_ACCOUNT]][CONF_ZONES]
        for zone in range(1, zones + 1):
            yield SIABinarySensor(
                port=entry.data[CONF_PORT],
                account=account_data[CONF_ACCOUNT],
                zone=zone,
                ping_interval=account_data[CONF_PING_INTERVAL],
                entry_id=entry.entry_id,
                entity_description=entity_description_smoke,
            )
            yield SIABinarySensor(
                port=entry.data[CONF_PORT],
                account=account_data[CONF_ACCOUNT],
                zone=zone,
                ping_interval=account_data[CONF_PING_INTERVAL],
                entry_id=entry.entry_id,
                entity_description=entity_description_moisture,
            )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SIA binary sensors from a config entry."""
    async_add_entities(generate_binary_sensors(entry))


class SIABinarySensor(SIABaseEntity, BinarySensorEntity):
    """Class for SIA Binary Sensors."""

    entity_description: SIABinarySensorEntityDescription

    def __init__(
        self,
        port: int,
        account: str,
        zone: int | None,
        ping_interval: int,
        entry_id: str,
        entity_description: SIABinarySensorEntityDescription,
    ) -> None:
        """Create SIABinarySensor object."""
        super().__init__(port, account, zone, ping_interval, entity_description)

        self._attr_unique_id = SIA_UNIQUE_ID_FORMAT_BINARY.format(
            entry_id,
            account,
            zone,
            entity_description.device_class,
        )

    def handle_last_state(self, last_state: State | None) -> None:
        """Handle the last state."""
        if last_state is not None and last_state.state is not None:
            if last_state.state == STATE_ON:
                self._attr_is_on = True
            elif last_state.state == STATE_OFF:
                self._attr_is_on = False
            elif last_state.state == STATE_UNAVAILABLE:
                self._attr_available = False

    def update_state(self, sia_event: SIAEvent) -> bool:
        """Update the state of the binary sensor."""
        new_state = self.entity_description.code_consequences.get(sia_event.code, None)
        if new_state is None:
            return False
        LOGGER.debug("New state will be %s", new_state)
        self._attr_is_on = new_state
        return True

    @callback
    def async_set_unavailable(self, _) -> None:
        """Set unavailable overridden to allow connectivity behaviour."""
        self._attr_available = False
        self.async_write_ha_state()
