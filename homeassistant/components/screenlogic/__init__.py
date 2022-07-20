"""The Screenlogic integration."""
from datetime import timedelta
import logging

from screenlogicpy import ScreenLogicError, ScreenLogicGateway
from screenlogicpy.const import (
    DATA as SL_DATA,
    EQUIPMENT,
    ON_OFF,
    SL_GATEWAY_IP,
    SL_GATEWAY_NAME,
    SL_GATEWAY_PORT,
    ScreenLogicWarning,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .config_flow import async_discover_gateways_by_unique_id, name_for_mac
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .services import async_load_screenlogic_services, async_unload_screenlogic_services

_LOGGER = logging.getLogger(__name__)


REQUEST_REFRESH_DELAY = 2
HEATER_COOLDOWN_DELAY = 6

# These seem to be constant across all controller models
PRIMARY_CIRCUIT_IDS = [500, 505]  # [Spa, Pool]

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Screenlogic from a config entry."""
    connect_info = await async_get_connect_info(hass, entry)

    gateway = ScreenLogicGateway(**connect_info)

    try:
        await gateway.async_connect()
    except ScreenLogicError as ex:
        _LOGGER.error("Error while connecting to the gateway %s: %s", connect_info, ex)
        raise ConfigEntryNotReady from ex

    coordinator = ScreenlogicDataUpdateCoordinator(
        hass, config_entry=entry, gateway=gateway
    )

    async_load_screenlogic_services(hass)

    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.gateway.async_disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)

    async_unload_screenlogic_services(hass)

    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_get_connect_info(hass: HomeAssistant, entry: ConfigEntry):
    """Construct connect_info from configuration entry and returns it to caller."""
    mac = entry.unique_id
    # Attempt to rediscover gateway to follow IP changes
    discovered_gateways = await async_discover_gateways_by_unique_id(hass)
    if mac in discovered_gateways:
        connect_info = discovered_gateways[mac]
    else:
        _LOGGER.warning("Gateway rediscovery failed")
        # Static connection defined or fallback from discovery
        connect_info = {
            SL_GATEWAY_NAME: name_for_mac(mac),
            SL_GATEWAY_IP: entry.data[CONF_IP_ADDRESS],
            SL_GATEWAY_PORT: entry.data[CONF_PORT],
        }

    return connect_info


class ScreenlogicDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage the data update for the Screenlogic component."""

    def __init__(self, hass, *, config_entry, gateway):
        """Initialize the Screenlogic Data Update Coordinator."""
        self.config_entry = config_entry
        self.gateway = gateway
        self.screenlogic_data = {}

        interval = timedelta(
            seconds=config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=interval,
            # Debounced option since the device takes
            # a moment to reflect the knock-on changes
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    async def _async_update_data(self):
        """Fetch data from the Screenlogic gateway."""
        try:
            await self.gateway.async_update()
        except ScreenLogicError as error:
            _LOGGER.warning("Update error - attempting reconnect: %s", error)
            await self._async_reconnect_update_data()
        except ScreenLogicWarning as warn:
            raise UpdateFailed(f"Incomplete update: {warn}") from warn

        return self.gateway.get_data()

    async def _async_reconnect_update_data(self):
        """Attempt to reconnect to the gateway and fetch data."""
        try:
            # Clean up the previous connection as we're about to create a new one
            await self.gateway.async_disconnect()

            connect_info = await async_get_connect_info(self.hass, self.config_entry)
            self.gateway = ScreenLogicGateway(**connect_info)

            await self.gateway.async_update()

        except (ScreenLogicError, ScreenLogicWarning) as ex:
            raise UpdateFailed(ex) from ex


class ScreenlogicEntity(CoordinatorEntity[ScreenlogicDataUpdateCoordinator]):
    """Base class for all ScreenLogic entities."""

    def __init__(self, coordinator, data_key, enabled=True):
        """Initialize of the entity."""
        super().__init__(coordinator)
        self._data_key = data_key
        self._enabled_default = enabled

    @property
    def entity_registry_enabled_default(self):
        """Entity enabled by default."""
        return self._enabled_default

    @property
    def mac(self):
        """Mac address."""
        return self.coordinator.config_entry.unique_id

    @property
    def unique_id(self):
        """Entity Unique ID."""
        return f"{self.mac}_{self._data_key}"

    @property
    def config_data(self):
        """Shortcut for config data."""
        return self.coordinator.data["config"]

    @property
    def gateway(self):
        """Return the gateway."""
        return self.coordinator.gateway

    @property
    def gateway_name(self):
        """Return the configured name of the gateway."""
        return self.gateway.name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the controller."""
        controller_type = self.config_data["controller_type"]
        hardware_type = self.config_data["hardware_type"]
        try:
            equipment_model = EQUIPMENT.CONTROLLER_HARDWARE[controller_type][
                hardware_type
            ]
        except KeyError:
            equipment_model = f"Unknown Model C:{controller_type} H:{hardware_type}"
        return DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self.mac)},
            manufacturer="Pentair",
            model=equipment_model,
            name=self.gateway_name,
            sw_version=self.gateway.version,
        )

    async def _async_refresh(self):
        """Refresh the data from the gateway."""
        await self.coordinator.async_refresh()
        # Second debounced refresh to catch any secondary
        # changes in the device
        await self.coordinator.async_request_refresh()

    async def _async_refresh_timed(self, now):
        """Refresh from a timed called."""
        await self.coordinator.async_request_refresh()


class ScreenLogicCircuitEntity(ScreenlogicEntity):
    """ScreenLogic circuit entity."""

    @property
    def name(self):
        """Get the name of the switch."""
        return f"{self.gateway_name} {self.circuit['name']}"

    @property
    def is_on(self) -> bool:
        """Get whether the switch is in on state."""
        return self.circuit["value"] == ON_OFF.ON

    async def async_turn_on(self, **kwargs) -> None:
        """Send the ON command."""
        await self._async_set_circuit(ON_OFF.ON)

    async def async_turn_off(self, **kwargs) -> None:
        """Send the OFF command."""
        await self._async_set_circuit(ON_OFF.OFF)

        # Turning off spa or pool circuit may require more time for the
        # heater to reflect changes depending on the pool controller,
        # so we schedule an extra refresh a bit farther out
        if self._data_key in PRIMARY_CIRCUIT_IDS:
            async_call_later(
                self.hass, HEATER_COOLDOWN_DELAY, self._async_refresh_timed
            )

    async def _async_set_circuit(self, circuit_value) -> None:
        if await self.gateway.async_set_circuit(self._data_key, circuit_value):
            _LOGGER.debug("Turn %s %s", self._data_key, circuit_value)
            await self._async_refresh()
        else:
            _LOGGER.warning(
                "Failed to set_circuit %s %s", self._data_key, circuit_value
            )

    @property
    def circuit(self):
        """Shortcut to access the circuit."""
        return self.coordinator.data[SL_DATA.KEY_CIRCUITS][self._data_key]
