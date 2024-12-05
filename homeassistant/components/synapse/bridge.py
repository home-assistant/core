import aiohttp
import asyncio
import binascii
import gzip
import io
import json
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CONFIGURATION_URL,
    ATTR_HW_VERSION,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SERIAL_NUMBER,
    ATTR_SUGGESTED_AREA,
    ATTR_SW_VERSION,
    ATTR_VIA_DEVICE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import async_get_platforms

from .const import DOMAIN, PLATFORMS, EVENT_NAMESPACE, SynapseApplication, SynapseMetadata
from .health import SynapseHealthSensor
RETRIES = 5

def hex_to_object(hex_str: str):
    compressed_data = binascii.unhexlify(hex_str)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed_data)) as f:
        json_str = f.read().decode('utf-8')
    return json.loads(json_str)

class SynapseBridge:
    """Manages a single synapse application"""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system"""
        self.logger = logging.getLogger(__name__)
        if config_entry is None:
            self.logger.error("application not online, reload integration after connecting")
            return

        self.config_entry = config_entry
        self.config_data: SynapseApplication = config_entry.data
        self.hass = hass
        self.device = None
        self.device_list = None
        self.app = None
        self.health: SynapseHealthSensor = None
        self.namespace = EVENT_NAMESPACE

        hass.data.setdefault(DOMAIN, {})[self.config_data.get("unique_id")] = self
        if self.config_data is not None:
          self.app = self.config_data.get("app")

    @property
    def hub_id(self) -> str:
        """ID reported by service"""
        return self.config_data.get("unique_id")

    def connected(self) -> bool:
        """Is the bridge currently online"""
        if self.health is not None:
            return self.health.online
        return False

    def cleanup_entities(self):
        # search out entities to remove
        # take the list of entities in the incoming payload, diff against current list
        # any unique id that currently exists that shouldn't gets a remove
        entity_registry = er.async_get(self.hass)
        for domain in PLATFORMS:
            incoming_list = self.config_data.get(domain)
            if incoming_list is None:
                continue

            found = []
            for incoming in incoming_list:
                found.append(incoming.get("unique_id"))

            # removing from inside the loop blows things up
            # create list to run as follow up
            remove = []
            for entity_id, entry in entity_registry.entities.items():
                if entry.platform == "synapse" and entry.config_entry_id == self.config_entry.entry_id:
                    # match based on unique_id, rm by entity_id
                    if entry.unique_id not in found:
                        remove.append(entry.entity_id)

            for entity_id in remove:
                entity_registry.async_remove(entity_id)

    def reload_devices(self):
        """Parse through the incoming payload, and set up devices to match"""
        self.device_list = {}
        device_registry = dr.async_get(self.hass)

        # create / update base device
        params = self.format_info()
        self.device = DeviceInfo(**params)
        device = device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            **params
        )

        # if the app declares secondary devices, register them also
        # use via_device to create an association with the base
        secondary_devices: list[SynapseMetadata] = self.config_data.get("secondary_devices",[])

        found = []
        for device in secondary_devices:
            self.logger.debug(f"secondary device {device.get("name")} => {device.get("name")}")
            params = self.format_info(device)
            params[ATTR_VIA_DEVICE] = (DOMAIN, self.config_data.get("unique_id"))

            self.device_list[device.get("unique_id")] = DeviceInfo(**params)
            device = device_registry.async_get_or_create(config_entry_id=self.config_entry.entry_id,**params)
            found.append(device.id)

    def format_info(self, device = None):
        device = device or self.config_data.get("device")
        return {
            ATTR_IDENTIFIERS: {
                (DOMAIN, self.config_data.get("unique_id"))
            },
            ATTR_CONFIGURATION_URL: device.get("configuration_url"),
            ATTR_MANUFACTURER: device.get("manufacturer"),
            ATTR_MODEL: device.get("model"),
            ATTR_NAME: device.get("name"),
            ATTR_HW_VERSION: device.get("hw_version"),
            ATTR_SERIAL_NUMBER: device.get("serial_number"),
            ATTR_SUGGESTED_AREA: device.get("suggested_area"),
            ATTR_SW_VERSION: device.get("sw_version"),
        }

    def event_name(self, event: str):
        """Standard format for event bus names to keep apps separate"""
        return f"{self.namespace}/{event}/{self.config_data.get("app")}"

    async def async_setup_health_sensor(self):
        """Setup the health sensor entity."""
        platform = async_get_platforms(self.hass, DOMAIN)
        # if platform:
        #     self.health = SynapseHealthSensor(self.hass, self.namespace, self.device, self.config_entry)
        #     await platform[0].async_add_entities([self.health])

    async def reload(self):
        """Attach reload call to gather new metadata & update local info"""
        self.logger.debug("reloading")

        # retry a few times
        # if ha recently rebooted, it may take a few seconds for the app to reconnect to socket
        data = None
        for x in range(0, 3):
            data = await self.identify(self.app)
            if data is not None:
                self.logger.debug(f"{self.app} success")
                break
            self.logger.debug(f"{self.app} wait 5s & retry")
            await asyncio.sleep(5)

        if data is None:
            self.logger.warning("no response, is app connected?")
            return

        # process data
        self.config_data = data
        self.reload_devices()
        self.cleanup_entities()

    async def wait_for_reload_reply(self, event_name):
        """Wait for reload reply event with hex string data payload, with a timeout of 2 seconds"""
        future = asyncio.Future()

        def handle_event(event):
            if not future.done():
                future.set_result(event.data['compressed'])

        self.hass.loop.call_soon_threadsafe(
            self.hass.bus.async_listen_once,
            event_name,
            handle_event
        )
        try:
            return await asyncio.wait_for(future, timeout=0.5)
        except asyncio.TimeoutError:
            return None

    async def identify(self, app: str):
        """Attach reload call to gather new metadata & update local info"""
        self.hass.bus.async_fire(f"{EVENT_NAMESPACE}/discovery/{app}")
        hex_str = await self.wait_for_reload_reply(f"{EVENT_NAMESPACE}/identify/{app}")
        if hex_str is None:
            return None
        return hex_to_object(hex_str)
