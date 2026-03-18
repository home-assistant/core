"""Support for EnOcean switches."""

from __future__ import annotations

from typing import Any

from enocean_async import EEP, EEP_SPECIFICATIONS, EEPHandler, EEPMessage, ERP1Telegram
from enocean_async.esp3.packet import ESP3PacketType
import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import CONF_ID, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, LOGGER
from .entity import EnOceanEntity, combine_hex

CONF_CHANNEL = "channel"
DEFAULT_NAME = "EnOcean Switch"

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_CHANNEL, default=0): cv.positive_int,
    }
)


def generate_unique_id(dev_id: list[int], channel: int) -> str:
    """Generate a valid unique id."""
    return f"{combine_hex(dev_id)}-{channel}"


def _migrate_to_new_unique_id(hass: HomeAssistant, dev_id, channel) -> None:
    """Migrate old unique ids to new unique ids."""
    old_unique_id = f"{combine_hex(dev_id)}"

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(Platform.SWITCH, DOMAIN, old_unique_id)

    if entity_id is not None:
        new_unique_id = generate_unique_id(dev_id, channel)
        try:
            ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)
        except ValueError:
            LOGGER.warning(
                "Skip migration of id [%s] to [%s] because it already exists",
                old_unique_id,
                new_unique_id,
            )
        else:
            LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                old_unique_id,
                new_unique_id,
            )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the EnOcean switch platform."""
    channel: int = config[CONF_CHANNEL]
    dev_id: list[int] = config[CONF_ID]
    dev_name: str = config[CONF_NAME]

    _migrate_to_new_unique_id(hass, dev_id, channel)
    async_add_entities([EnOceanSwitch(dev_id, dev_name, channel)])


class EnOceanSwitch(EnOceanEntity, SwitchEntity):
    """Representation of an EnOcean switch device."""

    _attr_is_on = False

    def __init__(self, dev_id: list[int], dev_name: str, channel: int) -> None:
        """Initialize the EnOcean switch device."""
        super().__init__(dev_id)
        self._light = None
        self.channel: int = channel
        self._attr_unique_id = generate_unique_id(dev_id, channel)
        self._attr_name = dev_name

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        if not self.address:
            return

        optional = [0x03]
        optional.extend(self.address.to_bytelist())
        optional.extend([0xFF, 0x00])
        self.send_command(
            data=[0xD2, 0x01, self.channel & 0xFF, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00],
            optional=optional,
            packet_type=ESP3PacketType(0x01),
        )
        self._attr_is_on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        if not self.address:
            return
        optional = [0x03]
        optional.extend(self.address.to_bytelist())
        optional.extend([0xFF, 0x00])
        self.send_command(
            data=[0xD2, 0x01, self.channel & 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
            optional=optional,
            packet_type=ESP3PacketType(0x01),
        )
        self._attr_is_on = False

    def value_changed(self, telegram: ERP1Telegram) -> None:
        """Update the internal state of the switch."""
        if telegram.rorg == 0xA5:
            # power meter telegram, turn on if > 1 watts
            if (eep := EEP_SPECIFICATIONS.get(EEP(0xA5, 0x12, 0x01))) is None:
                LOGGER.warning("EEP A5-12-01 cannot be decoded")
                return

            msg: EEPMessage = EEPHandler(eep).decode(telegram)

            if "DT" in msg.values and msg.values["DT"].raw == 1:
                # this packet reports the current value
                raw_val = msg.values["MR"].raw
                divisor = msg.values["DIV"].raw
                watts = raw_val / (10**divisor)
                if watts > 1:
                    self._attr_is_on = True
                    self.schedule_update_ha_state()

        elif telegram.rorg == 0xD2:
            # actuator status telegram
            if (eep := EEP_SPECIFICATIONS.get(EEP(0xD2, 0x01, 0x01))) is None:
                LOGGER.warning("EEP D2-01-01 cannot be decoded")
                return

            msg = EEPHandler(eep).decode(telegram)
            if msg.values["CMD"].raw == 4:
                channel = msg.values["I/O"].raw
                output = msg.values["OV"].raw
                if channel == self.channel:
                    self._attr_is_on = output > 0
                    self.schedule_update_ha_state()
