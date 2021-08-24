"""Code shared between all platforms."""
import asyncio
import logging

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_ENTITIES,
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_ID,
    CONF_PLATFORM,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.restore_state import RestoreEntity

from . import pytuya
from .const import (
    CONF_LOCAL_KEY,
    CONF_PRODUCT_KEY,
    CONF_PROTOCOL_VERSION,
    DOMAIN,
    TUYA_DEVICE,
)

_LOGGER = logging.getLogger(__name__)


def prepare_setup_entities(hass, config_entry, platform):
    """Prepare ro setup entities for a platform."""
    entities_to_setup = [
        entity
        for entity in config_entry.data[CONF_ENTITIES]
        if entity[CONF_PLATFORM] == platform
    ]
    if not entities_to_setup:
        return None, None

    tuyainterface = hass.data[DOMAIN][config_entry.entry_id][TUYA_DEVICE]

    return tuyainterface, entities_to_setup


async def async_setup_entry(
    domain, entity_class, flow_schema, hass, config_entry, async_add_entities
):
    """Set up a Tuya platform based on a config entry.

    This is a generic method and each platform should lock domain and
    entity_class with functools.partial.
    """
    tuyainterface, entities_to_setup = prepare_setup_entities(
        hass, config_entry, domain
    )
    if not entities_to_setup:
        return

    dps_config_fields = list(get_dps_for_platform(flow_schema))

    entities = []
    for device_config in entities_to_setup:
        # Add DPS used by this platform to the request list
        for dp_conf in dps_config_fields:
            if dp_conf in device_config:
                tuyainterface.dps_to_request[device_config[dp_conf]] = None

        entities.append(
            entity_class(
                tuyainterface,
                config_entry,
                device_config[CONF_ID],
            )
        )

    async_add_entities(entities)


def get_dps_for_platform(flow_schema):
    """Return config keys for all platform keys that depends on a datapoint."""
    for key, value in flow_schema(None).items():
        if hasattr(value, "container") and value.container is None:
            yield key.schema


def get_entity_config(config_entry, dp_id):
    """Return entity config for a given DPS id."""
    for entity in config_entry.data[CONF_ENTITIES]:
        if entity[CONF_ID] == dp_id:
            return entity
    raise Exception(f"missing entity config for id {dp_id}")


@callback
def async_config_entry_by_device_id(hass, device_id):
    """Look up config entry by device id."""
    current_entries = hass.config_entries.async_entries(DOMAIN)
    for entry in current_entries:
        if entry.data[CONF_DEVICE_ID] == device_id:
            return entry
    return None


class TuyaDevice(pytuya.TuyaListener, pytuya.ContextualLogger):
    """Cache wrapper for pytuya.TuyaInterface."""

    def __init__(self, hass, config_entry):
        """Initialize the cache."""
        super().__init__()
        self._hass = hass
        self._config_entry = config_entry
        self._interface = None
        self._status = {}
        self.dps_to_request = {}
        self._is_closing = False
        self._connect_task = None
        self.set_logger(_LOGGER, config_entry[CONF_DEVICE_ID])

        # This has to be done in case the device type is type_0d
        for entity in config_entry[CONF_ENTITIES]:
            self.dps_to_request[entity[CONF_ID]] = None

    @property
    def connected(self):
        """Return if connected to device."""
        return self._interface is not None

    def async_connect(self):
        """Connect to device if not already connected."""
        if not self._is_closing and self._connect_task is None and not self._interface:
            self._connect_task = asyncio.create_task(self._make_connection())

    async def _make_connection(self):
        self.debug("Connecting to %s", self._config_entry[CONF_HOST])

        try:
            self._interface = await pytuya.connect(
                self._config_entry[CONF_HOST],
                self._config_entry[CONF_DEVICE_ID],
                self._config_entry[CONF_LOCAL_KEY],
                float(self._config_entry[CONF_PROTOCOL_VERSION]),
                self,
            )
            self._interface.add_dps_to_request(self.dps_to_request)

            self.debug("Retrieving initial state")
            status = await self._interface.status()
            if status is None:
                raise Exception("Failed to retrieve status")

            self.status_updated(status)
        except Exception:  # pylint: disable=broad-except
            self.exception(f"Connect to {self._config_entry[CONF_HOST]} failed")
            if self._interface is not None:
                await self._interface.close()
                self._interface = None
        self._connect_task = None

    async def close(self):
        """Close connection and stop re-connect loop."""
        self._is_closing = True
        if self._connect_task is not None:
            self._connect_task.cancel()
            await self._connect_task
        if self._interface is not None:
            await self._interface.close()

    async def set_dp(self, state, dp_index):
        """Change value of a DP of the Tuya device."""
        if self._interface is not None:
            try:
                await self._interface.set_dp(state, dp_index)
            except Exception:  # pylint: disable=broad-except
                self.exception("Failed to set DP %d to %d", dp_index, state)
        else:
            self.error(
                "Not connected to device %s", self._config_entry[CONF_FRIENDLY_NAME]
            )

    async def set_dps(self, states):
        """Change value of a DPs of the Tuya device."""
        if self._interface is not None:
            try:
                await self._interface.set_dps(states)
            except Exception:  # pylint: disable=broad-except
                self.exception("Failed to set DPs %r", states)
        else:
            self.error(
                "Not connected to device %s", self._config_entry[CONF_FRIENDLY_NAME]
            )

    @callback
    def status_updated(self, status):
        """Device updated status."""
        self._status.update(status)

        signal = f"localtuya_{self._config_entry[CONF_DEVICE_ID]}"
        async_dispatcher_send(self._hass, signal, self._status)

    @callback
    def disconnected(self):
        """Device disconnected."""
        signal = f"localtuya_{self._config_entry[CONF_DEVICE_ID]}"
        async_dispatcher_send(self._hass, signal, None)

        self._interface = None
        self.debug("Disconnected - waiting for discovery broadcast")


class LocalTuyaEntity(RestoreEntity, pytuya.ContextualLogger):
    """Representation of a Tuya entity."""

    def __init__(self, device, config_entry, dp_id, logger, **kwargs):
        """Initialize the Tuya entity."""
        super().__init__()
        self._device = device
        self._config_entry = config_entry
        self._config = get_entity_config(config_entry, dp_id)
        self._dp_id = dp_id
        self._status = {}
        self.set_logger(logger, self._config_entry.data[CONF_DEVICE_ID])

    async def async_added_to_hass(self):
        """Subscribe localtuya events."""
        await super().async_added_to_hass()

        self.debug("Adding %s with configuration: %s", self.entity_id, self._config)

        state = await self.async_get_last_state()
        if state:
            self.status_restored(state)

        def _update_handler(status):
            """Update entity state when status was updated."""
            if status is not None:
                self._status = status
                self.status_updated()
            else:
                self._status = {}

            self.schedule_update_ha_state()

        signal = f"localtuya_{self._config_entry.data[CONF_DEVICE_ID]}"
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, _update_handler)
        )

    @property
    def device_info(self):
        """Return device information for the device registry."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, f"local_{self._config_entry.data[CONF_DEVICE_ID]}")
            },
            "name": self._config_entry.data[CONF_FRIENDLY_NAME],
            "manufacturer": "Unknown",
            "model": self._config_entry.data.get(CONF_PRODUCT_KEY, "Tuya generic"),
            "sw_version": self._config_entry.data[CONF_PROTOCOL_VERSION],
        }

    @property
    def name(self):
        """Get name of Tuya entity."""
        return self._config[CONF_FRIENDLY_NAME]

    @property
    def should_poll(self):
        """Return if platform should poll for updates."""
        return False

    @property
    def unique_id(self):
        """Return unique device identifier."""
        return f"local_{self._config_entry.data[CONF_DEVICE_ID]}_{self._dp_id}"

    def has_config(self, attr):
        """Return if a config parameter has a valid value."""
        value = self._config.get(attr, "-1")
        return value is not None and value != "-1"

    @property
    def available(self):
        """Return if device is available or not."""
        return str(self._dp_id) in self._status

    def dps(self, dp_index):
        """Return cached value for DPS index."""
        value = self._status.get(str(dp_index))
        if value is None:
            self.warning(
                "Entity %s is requesting unknown DPS index %s",
                self.entity_id,
                dp_index,
            )

        return value

    def dps_conf(self, conf_item):
        """Return value of datapoint for user specified config item.

        This method looks up which DP a certain config item uses based on
        user configuration and returns its value.
        """
        dp_index = self._config.get(conf_item)
        if dp_index is None:
            self.warning(
                "Entity %s is requesting unset index for option %s",
                self.entity_id,
                conf_item,
            )
        return self.dps(dp_index)

    def status_updated(self):
        """Device status was updated.

        Override in subclasses and update entity specific state.
        """

    def status_restored(self, stored_state):
        """Device status was restored.

        Override in subclasses and update entity specific state.
        """
