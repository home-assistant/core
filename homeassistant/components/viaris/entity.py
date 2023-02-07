"""MQTT component mixins and helpers."""
import logging

from homeassistant import config_entries
from homeassistant.helpers.entity import DeviceInfo, Entity

# from . import ViarisEntityDescription, ViarisEntityDescription2
from . import ViarisEntityDescription
from .const import (  # CONF_TOPIC_PREFIX,
    CONF_SERIAL_NUMBER,
    DEFAULT_TOPIC_PREFIX,
    DEVICE_INFO_MANUFACTURER,
    DEVICE_INFO_MODEL,
    DOMAIN,
    MODEL_COMBIPLUS,
    MODEL_UNI,
    SERIAL_PREFIX_UNI,
)

_LOGGER = logging.getLogger(__name__)


class ViarisEntity(Entity):
    """Common viaris entity."""

    def __init__(
        self,
        config_entry: config_entries.ConfigEntry,
        description: ViarisEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        # topic_prefix = config_entry.data[CONF_TOPIC_PREFIX]
        topic_prefix = DEFAULT_TOPIC_PREFIX
        serial_number = config_entry.data[CONF_SERIAL_NUMBER]

        self._topic_rt_subs = f"{topic_prefix}0{serial_number[-5:]}/stat/0/{serial_number}/streamrt/modulator"

        self.entity_id = f"{description.domain}.{serial_number}_{description.key}"
        self._attr_unique_id = "-".join(
            [serial_number, description.domain, description.key, description.attribute]
        )
        self._topic_rt_pub = (
            f"{topic_prefix}0{serial_number[-5:]}/set/0/{serial_number}/rt/modulator"
        )
        if serial_number[0:5] == SERIAL_PREFIX_UNI:
            self._model = MODEL_UNI
            self._topic_evsm_mennekes_pub = f"{topic_prefix}0{serial_number[-5:]}/get/0/{serial_number}/value/evsm/mennekes"
            self._topic_evsm_mennekes_subs = f"{topic_prefix}0{serial_number[-5:]}/stat/0/{serial_number}/evt/evsm/mennekes"
            self._topic_evsm_menek_value_subs = f"{topic_prefix}0{serial_number[-5:]}/stat/0/{serial_number}/value/evsm/mennekes"
        else:
            self._model = MODEL_COMBIPLUS
            self._topic_evsm_mennekes_pub = f"{topic_prefix}0{serial_number[-5:]}/get/0/{serial_number}/value/evsm/mennekes1"
            self._topic_evsm_mennekes_subs = f"{topic_prefix}0{serial_number[-5:]}/stat/0/{serial_number}/evt/evsm/mennekes1"
            self._topic_evsm_menek_value_subs = f"{topic_prefix}0{serial_number[-5:]}/stat/0/{serial_number}/value/evsm/mennekes1"
            self._topic_evsm_mennekes2_pub = f"{topic_prefix}0{serial_number[-5:]}/get/0/{serial_number}/value/evsm/mennekes2"
            self._topic_evsm_mennekes2_subs = f"{topic_prefix}0{serial_number[-5:]}/stat/0/{serial_number}/evt/evsm/mennekes2"
            self._topic_evsm_menek2_value_subs = f"{topic_prefix}0{serial_number[-5:]}/stat/0/{serial_number}/value/evsm/mennekes2"

        # self._topic_evsm_schuko_pub = f"{topic_prefix}0{serial_number[-5:]}/get/0/{serial_number}/value/evsm/schuko"
        # self._topic_evsm_schuko_subs = f"{topic_prefix}0{serial_number[-5:]}/stat/0/{serial_number}/evt/evsm/schuko"
        # self._topic_evsm_schuko_value_subs = f"{topic_prefix}0{serial_number[-5:]}/stat/0/{serial_number}/value/evsm/schuko"

        self._topic_boot_sys_pub = (
            f"{topic_prefix}0{serial_number[-5:]}/get/0/{serial_number}/boot/sys"
        )
        self._topic_boot_sys_subs = (
            f"{topic_prefix}0{serial_number[-5:]}/stat/0/{serial_number}/boot/sys"
        )
        self._topic_init_boot_sys_subs = (
            f"{topic_prefix}0{serial_number[-5:]}/stat/0/{serial_number}/init_boot/sys"
        )
        self._topic_mqtt_pub = (
            f"{topic_prefix}0{serial_number[-5:]}/get/0/{serial_number}/cfg/mqtt_user"
        )
        self._topic_mqtt_subs = (
            f"{topic_prefix}0{serial_number[-5:]}/stat/0/{serial_number}/cfg/mqtt_user"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=config_entry.title,
            manufacturer=DEVICE_INFO_MANUFACTURER,
            model=DEVICE_INFO_MODEL,
        )
