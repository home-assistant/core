"""Support for EnOcean switches."""
from __future__ import annotations

from enocean.protocol.constants import RORG
from typing import Any
from enocean.utils import combine_hex
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_ID, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, LOGGER
from .device import EnOceanEntity

CONF_CHANNEL = "channel"
DEFAULT_NAME = "EnOcean Switch"
CONF_BASE_ID = "base_id"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_CHANNEL, default=0): cv.positive_int,
        vol.Optional(CONF_BASE_ID, default=[0x00, 0x00, 0x00, 0x00]): vol.All(
            cv.ensure_list, [vol.Coerce(int)]
        ),
    }
)


def generate_unique_id(dev_id: list[int], channel: int) -> str:
    """Generate a valid unique id."""
    return f"{combine_hex(dev_id)}-{channel}"


def _migrate_to_new_unique_id(hass: HomeAssistant, dev_id, channel) -> None:
    """Migrate old unique ids to new unique ids."""
    old_unique_id = f"{combine_hex(dev_id)}"

    ent_reg = entity_registry.async_get(hass)
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
    channel = config.get(CONF_CHANNEL)
    dev_id = config.get(CONF_ID)
    dev_name = config.get(CONF_NAME)
    base_id = config.get(CONF_BASE_ID, [0, 0, 0, 0])

    _migrate_to_new_unique_id(hass, dev_id, channel)
    async_add_entities([EnOceanSwitch(dev_id, dev_name, channel, base_id)])


class EnOceanSwitch(EnOceanEntity, SwitchEntity):
    """Representation of an EnOcean switch device."""

    def __init__(self, dev_id, dev_name, channel, base_id):
        """Initialize the EnOcean switch device."""
        super().__init__(dev_id, dev_name)
        self._light = None
        self._on_state = False
        self._on_state2 = False
        self.channel = channel
        self.base_id = base_id
        self._attr_unique_id = generate_unique_id(dev_id, channel)

    @property
    def is_on(self):
        """Return whether the switch is on or off."""
        return self._on_state

    @property
    def name(self):
        """Return the device name."""
        return self.dev_name

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        # build the data and optional data for the serial packet
        optional = [0x03]  # number of subtelegram
        optional.extend(self.dev_id)  # destination id
        optional.extend(
            [0xFF, 0x00]
        )  # dBm for send case: 0xFF and security level 0 (telegram not processed)
        channel = self.channel & 0xFF
        data = [RORG.VLD, 0x01]
        data.extend([channel])
        data.extend([0x64])  # value to set: 0x64 = 100 = 100%
        data.extend(self.base_id)  # append base id if given in config
        data.extend([0x00])

        self.send_command(
            # radio variant VLD (RORG: D2), payload: 0x01 -> Command 01, channel, ,
            # channel == 0x1E??
            # data=[0xD2, 0x01, self.channel & 0xFF, 0x64, 0xFF, 0xD9, 0x7F, 0x80, 0x00],
            data=data,
            optional=optional,
            packet_type=0x01,  # RADIO_ERP1 (radio telegram)
        )
        self._on_state = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        optional = [0x03]
        optional.extend(self.dev_id)
        optional.extend([0xFF, 0x00])
        channel = self.channel & 0xFF
        data = [RORG.VLD, 0x01]
        data.extend([channel])
        data.extend([0x00])  # value to set: 0
        data.extend(self.base_id)
        data.extend([0x00])

        self.send_command(
            # data=[0xD2, 0x01, self.channel & 0xFF, 0x00, 0xFF, 0xD9, 0x7F, 0x80, 0x00],
            data=data,
            optional=optional,
            packet_type=0x01,
        )
        self._on_state = False

    def value_changed(self, packet):
        """Update the internal state of the switch."""
        if packet.data[0] == 0xA5:
            # power meter telegram, turn on if > 10 watts
            packet.parse_eep(0x12, 0x01)
            if packet.parsed["DT"]["raw_value"] == 1:
                raw_val = packet.parsed["MR"]["raw_value"]
                divisor = packet.parsed["DIV"]["raw_value"]
                watts = raw_val / (10**divisor)
                if watts > 1:
                    self._on_state = True
                    self.schedule_update_ha_state()
        elif packet.data[0] == 0xD2:
            # actuator status telegram
            packet.parse_eep(0x01, 0x01)
            if packet.parsed["CMD"]["raw_value"] == 4:
                channel = packet.parsed["IO"]["raw_value"]
                output = packet.parsed["OV"]["raw_value"]
                if channel == self.channel:
                    self._on_state = output > 0
                    self.schedule_update_ha_state()
