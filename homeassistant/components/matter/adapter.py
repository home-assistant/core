"""Matter to Home Assistant adapter."""
from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Callable
import json
import logging
from typing import TYPE_CHECKING

import aiohttp
from matter_server.client.adapter import AbstractMatterAdapter
from matter_server.client.model.node_device import AbstractMatterNodeDevice
from matter_server.common.json_utils import CHIPJSONDecoder, CHIPJSONEncoder
from matter_server.vendor.chip.clusters import Objects as all_clusters

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .device_platform import DEVICE_PLATFORM

if TYPE_CHECKING:
    from matter_server.client.model.node import MatterNode

STORAGE_MAJOR_VERSION = 1
STORAGE_MINOR_VERSION = 0


def load_json(
    filename: str, default: list | dict | None = None, decoder=None
) -> list | dict:
    """Load JSON data from a file and return as dict or list.

    Defaults to returning empty dict if file is not found.

    Temporarily copied from Home Assistant to allow decoder.
    """
    try:
        with open(filename, encoding="utf-8") as fdesc:
            return json.loads(fdesc.read(), cls=decoder)
    except FileNotFoundError:
        # This is not a fatal error
        logging.getLogger(__name__).debug("JSON file not found: %s", filename)
    except ValueError as error:
        logging.getLogger(__name__).exception(
            "Could not parse JSON content: %s", filename
        )
        raise HomeAssistantError(error) from error
    except OSError as error:
        logging.getLogger(__name__).exception("JSON file reading failed: %s", filename)
        raise HomeAssistantError(error) from error
    return {} if default is None else default


class MatterStore(Store):
    """Temporary fork to add support for using our JSON decoder."""

    async def _async_load_data(self):
        """Load the data with custom decoder."""
        # Check if we have a pending write
        if self._data is not None:
            return await super()._async_load_data()

        data = await self.hass.async_add_executor_job(
            load_json, self.path, None, CHIPJSONDecoder
        )

        if data == {}:
            return None

        # We store it as a to-be-saved data so the load function will pick it up
        # and run migration etc.
        self._data = data
        return await super()._async_load_data()


def get_matter_store(hass: HomeAssistant, config_entry: ConfigEntry) -> MatterStore:
    """Get the store for the config entry."""
    return MatterStore(
        hass,
        STORAGE_MAJOR_VERSION,
        f"{DOMAIN}_{config_entry.entry_id}",
        minor_version=STORAGE_MINOR_VERSION,
        encoder=CHIPJSONEncoder,
    )


def get_matter_fallback_store(hass: HomeAssistant, config_entry: ConfigEntry) -> Store:
    """Get the store for the config entry."""
    return Store(
        hass,
        STORAGE_MAJOR_VERSION,
        f"{DOMAIN}_{config_entry.entry_id}",
        minor_version=STORAGE_MINOR_VERSION,
    )


class MatterAdapter(AbstractMatterAdapter):
    """Connect Matter into Home Assistant."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the adapter."""
        self.hass = hass
        self.config_entry = config_entry
        self.logger = logging.getLogger(__name__)
        self._store = get_matter_store(hass, config_entry)
        self.platform_handlers: dict[Platform, AddEntitiesCallback] = {}
        self._platforms_set_up = asyncio.Event()
        self._node_lock: dict[int, asyncio.Lock] = {}

    def register_platform_handler(
        self, platform: Platform, add_entities: AddEntitiesCallback
    ) -> None:
        """Register a platform handler."""
        self.platform_handlers[platform] = add_entities
        if len(self.platform_handlers) == len(DEVICE_PLATFORM):
            self._platforms_set_up.set()

    @abstractmethod
    async def load_data(self) -> dict | None:
        """Load data."""
        try:
            return await self._store.async_load()
        except ValueError:
            # Exception happens when the stored data is not deserializable with new Matter models
            data = await get_matter_fallback_store(
                self.hass, self.config_entry
            ).async_load()
            # Remove the serialized matter data. Devices will be re-interviewed.
            if data is not None:
                del data["node_interview_version"]
            return data

    @abstractmethod
    async def save_data(self, data: dict) -> None:
        """Save data."""
        await self._store.async_save(data)

    @abstractmethod
    def delay_save_data(self, get_data: Callable[[], dict]) -> None:
        """Save data, but not right now."""
        self._store.async_delay_save(get_data, 60)

    def get_server_url(self) -> str:
        """Get the server URL."""
        return self.config_entry.data[CONF_URL]

    def get_client_session(self) -> aiohttp.ClientSession:
        """Get the client session."""
        return async_get_clientsession(self.hass)

    def get_node_lock(self, nodeid) -> asyncio.Lock:
        """Get the lock for a node."""
        if nodeid not in self._node_lock:
            self._node_lock[nodeid] = asyncio.Lock()
        return self._node_lock[nodeid]

    async def setup_node(self, node: MatterNode) -> None:
        """Set up an node."""
        await self._platforms_set_up.wait()
        self.logger.debug("Setting up entities for node %s", node.node_id)

        bridge_unique_id: str | None = None

        if node.aggregator_device_type_instance is not None:
            node_info = node.root_device_type_instance.get_cluster(all_clusters.Basic)
            self._create_device_registry(
                node_info, node_info.nodeLabel or "Hub device", None
            )
            bridge_unique_id = node_info.uniqueID

        for node_device in node.node_devices:
            self._setup_node_device(node_device, bridge_unique_id)

    def _create_device_registry(
        self,
        info: all_clusters.Basic | all_clusters.BridgedDeviceBasic,
        name: str,
        bridge_unique_id: str | None,
    ) -> None:
        """Create a device registry entry."""
        dr.async_get(self.hass).async_get_or_create(
            name=name,
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, info.uniqueID)},
            hw_version=info.hardwareVersionString,
            sw_version=info.softwareVersionString,
            manufacturer=info.vendorName,
            model=info.productName,
            via_device=(DOMAIN, bridge_unique_id) if bridge_unique_id else None,
        )

    def _setup_node_device(
        self, node_device: AbstractMatterNodeDevice, bridge_unique_id: str | None
    ) -> None:
        """Set up a node device."""
        node = node_device.node()
        basic_info = node_device.device_info()
        device_type_instances = node_device.device_type_instances()

        name = basic_info.nodeLabel
        if not name and device_type_instances:
            name = f"{device_type_instances[0].device_type.__doc__[:-1]} {node.node_id}"

        self._create_device_registry(basic_info, name, bridge_unique_id)

        for instance in device_type_instances:
            created = False

            for platform, devices in DEVICE_PLATFORM.items():
                entity_descriptions = devices.get(instance.device_type)

                if entity_descriptions is None:
                    continue

                if not isinstance(entity_descriptions, list):
                    entity_descriptions = [entity_descriptions]

                entities = []
                for entity_description in entity_descriptions:
                    self.logger.debug(
                        "Creating %s entity for %s (%s)",
                        platform,
                        instance.device_type.__name__,
                        hex(instance.device_type.device_type),
                    )
                    entities.append(
                        entity_description.entity_cls(
                            node_device, instance, entity_description
                        )
                    )

                self.platform_handlers[platform](entities)
                created = True

            if not created:
                self.logger.warning(
                    "Found unsupported device %s (%s)",
                    type(instance).__name__,
                    hex(instance.device_type.device_type),
                )

    async def handle_server_disconnected(self, should_reload: bool) -> None:
        """Handle server disconnected."""
        # The entry needs to be reloaded since a new driver state
        # will be acquired on reconnect.
        # All model instances will be replaced when the new state is acquired.
        if should_reload and self.hass.is_running:
            self.logger.info("Disconnected from server. Reloading")
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )
