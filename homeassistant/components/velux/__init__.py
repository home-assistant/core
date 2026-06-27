"""Support for VELUX KLF 200 devices."""

import dataclasses

from pyvlx import OpeningDevice, PyVLX, PyVLXException, Window
from pyvlx.const import Velocity
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER, PLATFORMS, PYVLX_FROM_CONFIG_FLOW, VELOCITY_MAP
from .coordinator import VeluxLimitationCoordinator
from .entity import velux_unique_id


@dataclasses.dataclass
class VeluxData:
    """Runtime data for a Velux config entry."""

    pyvlx: PyVLX
    limitation_coordinators: dict[int, VeluxLimitationCoordinator]


type VeluxConfigEntry = ConfigEntry[VeluxData]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _find_opening_device_node(
    hass: HomeAssistant, device_id: str
) -> OpeningDevice | None:
    """Find the OpeningDevice node for a device registry ID.

    Returns the node if found, or None if the device doesn't exist or isn't
    an opening device.
    """
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        return None

    for identifier in device.identifiers:
        if identifier[0] != DOMAIN:
            continue
        node_identifier = identifier[1]
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED:
                continue
            for node in entry.runtime_data.pyvlx.nodes:
                if velux_unique_id(
                    node, entry.entry_id
                ) == node_identifier and isinstance(node, OpeningDevice):
                    return node
        break

    return None


def _set_node_velocity(node: OpeningDevice, velocity: Velocity) -> None:
    """Apply velocity setting to a node."""
    if velocity == Velocity.DEFAULT:
        node.use_default_velocity = False
        node.default_velocity = Velocity.DEFAULT
    else:
        node.use_default_velocity = True
        node.default_velocity = velocity


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Velux component."""

    async def async_set_velocity(service_call: ServiceCall) -> None:
        """Set velocity for a Velux opening device."""
        velocity = VELOCITY_MAP[service_call.data["velocity"]]
        device_id: str = service_call.data["device_id"]

        node = _find_opening_device_node(hass, device_id)
        if node is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"device_id": device_id},
            )

        _set_node_velocity(node, velocity)

    hass.services.async_register(
        DOMAIN,
        "set_velocity",
        async_set_velocity,
        schema=vol.Schema(
            {
                vol.Required("device_id"): cv.string,
                vol.Required("velocity"): vol.In(list(VELOCITY_MAP)),
            }
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: VeluxConfigEntry) -> bool:
    """Set up the velux component."""
    host = entry.data[CONF_HOST]
    password = entry.data[CONF_PASSWORD]

    # Prefer the already-connected instance passed from the config flow so that
    # we do not force a disconnect/reboot between connection validation and setup.
    # Falls back to creating a fresh instance on HA restart or reload.
    pyvlx: PyVLX | None = hass.data.get(PYVLX_FROM_CONFIG_FLOW, {}).pop(host, None)
    if pyvlx is None:
        pyvlx = PyVLX(host=host, password=password)

    try:
        LOGGER.debug("Ensuring connection to Velux gateway %s", host)
        await pyvlx.ensure_connected()
        LOGGER.debug("Retrieving scenes from %s", host)
        await pyvlx.load_scenes()
        LOGGER.debug("Retrieving nodes from %s", host)
        await pyvlx.load_nodes()
    except (OSError, PyVLXException) as ex:
        # Since pyvlx raises the same exception for auth and connection errors,
        # we need to check the exception message to distinguish them.
        # Ultimately this should be fixed in pyvlx to raise specialized exceptions,
        # right now it's been a while since the last pyvlx
        # release, so we do this workaround here.
        if (
            isinstance(ex, PyVLXException)
            and ex.description == "Login to KLF 200 failed, check credentials"
        ):
            raise ConfigEntryAuthFailed(
                f"Invalid authentication for Velux gateway at {host}"
            ) from ex

        # Defer setup and retry later as the bridge is not ready/available
        raise ConfigEntryNotReady(
            f"Unable to connect to Velux gateway at {host}. "
            "If connection continues to fail, try power-cycling the gateway device."
        ) from ex

    LOGGER.debug("Velux connection to %s successful", host)

    limitation_coordinators: dict[int, VeluxLimitationCoordinator] = {}
    for node in pyvlx.nodes:
        if isinstance(node, Window) and node.rain_sensor:
            coordinator = VeluxLimitationCoordinator(hass, entry, node)
            # do not await coordinator.async_config_entry_first_refresh() here to avoid doing
            # it for disabled entities, the entities will call it when they are added to hass
            limitation_coordinators[node.node_id] = coordinator

    entry.runtime_data = VeluxData(
        pyvlx=pyvlx, limitation_coordinators=limitation_coordinators
    )

    connections = None
    if (mac := entry.data.get(CONF_MAC)) is not None:
        connections = {(dr.CONNECTION_NETWORK_MAC, mac)}

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"gateway_{entry.entry_id}")},
        name="KLF 200 Gateway",
        manufacturer="Velux",
        model="KLF 200",
        hw_version=(
            str(pyvlx.klf200.version.hardwareversion) if pyvlx.klf200.version else None
        ),
        sw_version=(
            str(pyvlx.klf200.version.softwareversion) if pyvlx.klf200.version else None
        ),
        connections=connections,
    )

    async def on_hass_stop(_: Event) -> None:
        """Close connection when hass stops."""
        LOGGER.debug("Velux interface terminated")
        await pyvlx.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VeluxConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Disconnect from gateway only after platforms are successfully unloaded.
        # Disconnecting will reboot the gateway in the pyvlx
        # library, which is needed to allow new
        # connections to be made later.
        await entry.runtime_data.pyvlx.disconnect()
    return unload_ok
