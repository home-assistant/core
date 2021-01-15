"""EBUS Integration."""
import asyncio
import collections
import logging
from typing import Dict

from pyebus import CircuitMap, Ebus, FieldDef, get_icon

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    API,
    CONF_MESSAGES,
    DOMAIN,
    PRIO,
    TTL,
    UNDO_UPDATE_LISTENER,
    UNIT_DEVICE_CLASS_MAP,
)

PLATFORMS = ["sensor"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set Up The Ebus Component."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set Up A Config Entry."""
    undo_listener = config_entry.add_update_listener(update_listener)
    api = EbusApi(hass, config_entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        API: api,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    await api.async_init()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload A Config Entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][config_entry.entry_id][UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass, config_entry):
    """Handle Options Update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class EbusApi:
    """EBUS API."""

    def __init__(self, hass: HomeAssistantType, entry: ConfigEntry):
        """EBUS API."""
        self._hass = hass
        self._entry = entry
        self._data = {}
        self._listener = collections.defaultdict(list)

        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        self.ebus = Ebus(host, port)
        self.circuitmap = CircuitMap(
            {
                "broadcast": "*",
                "bai": "Heater",
                "bc": "Burner",
                "hc": "Heating",
                "mc": "Mixer",
                "hwc": "Water",
                "cc": "Circulation",
                "sc": "Solar",
            }
        )

    @property
    def ident(self):
        """Ident."""
        return f"{self.ebus.host}:{self.ebus.port}"

    async def async_init(self):
        """Initialize."""
        ebus = self.ebus
        async for _ in self.ebus.wait_scancompleted():
            pass
        await ebus.load_msgdefs()
        messages = self._entry.data[CONF_MESSAGES]
        if messages:
            ebus.msgdefs = ebus.msgdefs.resolve(messages)
        self._hass.async_create_task(self.observe())

    async def observe(self):
        """Observe EBUS."""
        data = self._data
        broken = False
        while True:
            try:
                async for msg in self.ebus.observe(
                    setprio=True, defaultprio=PRIO, ttl=TTL
                ):
                    broken = False
                    _LOGGER.info(msg)
                    if msg.valid:
                        for field in msg.fields:
                            data[field.fielddef.ident] = field.value
                            self.notify(field.fielddef)
                    else:
                        # remove outdated values
                        for fielddef in msg.msgdef.fields:
                            data.pop(fielddef.ident, None)
                            self.notify(fielddef)
            except Exception as exc:
                if not broken:
                    _LOGGER.error(exc)
                broken = True
                await asyncio.sleep(60)

    def notify(self, fielddef):
        """Notify about field update."""
        for entity in self._listener[fielddef.ident]:
            entity.async_write_ha_state()

    @callback
    def subscribe(self, entity, fielddef):
        """Subscribe an entity from API fetches."""
        self._listener[fielddef.ident].append(entity)

        @callback
        def unsubscribe() -> None:
            """Unsubscribe an entity from API fetches (when disable)."""
            self._listener[fielddef.ident].remove(entity)

        return unsubscribe

    def get_state(self, fielddef):
        """Get Field State."""
        return self._data.get(fielddef.ident, None)

    def get_available(self, fielddef):
        """Get Field Available."""
        return fielddef.ident in self._data


class EbusEntity(Entity):
    """EBUS Entity."""

    def __init__(self, api: EbusApi, ident: str):
        """EBUS Entity."""
        super().__init__()
        self._api = api
        self._unique_id = f"{api.ident}-{ident}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._api.ident)},
            "name": "EBUS",
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False


class EbusFieldEntity(EbusEntity):
    """EBUS Entity."""

    def __init__(self, api: EbusApi, fielddef: FieldDef):
        """EBUS Entity."""
        super().__init__(api, fielddef.ident)
        self._fielddef = fielddef
        self._device_class = UNIT_DEVICE_CLASS_MAP.get(self._fielddef.unit, None)

    @property
    def name(self) -> str:
        """Return the name."""
        fielddef = self._fielddef
        msgdef = fielddef.parent
        circuit = self._api.circuitmap.get_humanname(msgdef.circuit)
        return f"{circuit} {msgdef.name} {fielddef.name}"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return get_icon(self._fielddef)

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit the value is expressed in."""
        return self._fielddef.unit

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return self._device_class

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_on_remove(self._api.subscribe(self, self._fielddef))

    @property
    def device_state_attributes(self):
        """Device State Attributes."""
        return {
            "Identifier": self._fielddef.ident,
            "Writeable": "Yes" if self._fielddef.parent.write else "No",
            "Values": self._fielddef.type_.comment,
        }
