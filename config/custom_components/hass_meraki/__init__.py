"""The Cisco Meraki Integration."""

from datetime import timedelta
import functools
import logging

import meraki

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

DOMAIN = "hass_meraki"
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Meraki from a config entry."""

    api_key = entry.data.get("api_key")
    org_id = entry.data.get("org_id")
    network_id = entry.data.get("network_id")

    if not api_key:
        _LOGGER.error("API Key is missing!")
        return False

    dashboard = meraki.DashboardAPI(api_key=api_key, suppress_logging=True)

    async def _get_neighbors(serial):
        """Call the Meraki API to get LLDP/CDP neighbor data for a device."""
        try:
            return await hass.async_add_executor_job(
                dashboard.devices.getDeviceLldpCdp, serial
            )
        except meraki.APIError as err:
            _LOGGER.error("Failed to get neighbors for serial %s: %s", serial, err)
            return False

    async def async_update_data():
        """Fetch latest device data and update active PoE port information."""
        data = {}
        try:
            # Determine which networks to query
            if network_id:
                networks = [{"id": network_id}]
            else:
                networks = await hass.async_add_executor_job(
                    dashboard.organizations.getOrganizationNetworks, org_id
                )

            # Get all devices in the organization
            all_devices = await hass.async_add_executor_job(
                dashboard.organizations.getOrganizationDevices, org_id
            )

            # Get availability info for these devices
            devices_availabilities = await hass.async_add_executor_job(
                dashboard.organizations.getOrganizationDevicesAvailabilities,
                org_id,
            )

            # Get port usage information
            port_usage = await hass.async_add_executor_job(
                functools.partial(
                    dashboard.switch.getOrganizationSwitchPortsUsageHistoryByDeviceByInterval,
                    org_id,
                    timespan=900,
                )
            )

            # Filter devices by network if network_id is provided
            if network_id:
                all_devices = [
                    device
                    for device in all_devices
                    if device.get("networkId") == network_id
                ]

            # Create an availability map keyed by serial
            avail_map = {item["serial"]: item for item in devices_availabilities}

            # Save static device properties in data
            for device in all_devices:
                serial = device.get("serial")
                if not serial:
                    continue

                device_avail = avail_map.get(serial, {})
                status = device_avail.get("status", "Unknown")

                data[serial] = {
                    "name": device.get("name", f"Meraki Device {serial}"),
                    "model": device.get("model", "Unknown"),
                    "firmware": device.get("firmware", "Unknown"),
                    "mac": device.get("mac", "Unknown"),
                    "networkId": device.get("networkId"),
                    "serial": serial,
                    "productType": device.get("productType", None),
                    "state": status,
                    "client_count": 0,
                    "clients": {},
                    # Use a dict to store port-specific details keyed by port id.
                    "active_poe_ports": {},
                }

            port_usage = port_usage.get("items")

            if network_id:
                port_usage = [
                    switch
                    for switch in port_usage
                    if switch.get("networkId") == network_id
                ]

            # Get or initialize a set to track already dispatched unique IDs.
            dispatched_ports = hass.data[DOMAIN].setdefault("dispatched_ports", set())

            # Process port usage for each switch
            for switch in port_usage:
                serial = switch.get("serial")
                if not serial:
                    continue

                active_poe_ports = {}
                ports = switch.get("ports") or []
                for port in ports:
                    port_id = port.get("portId")
                    intervals = port.get("intervals")
                    if intervals and isinstance(intervals, list) and len(intervals) > 0:
                        energy = intervals[0].get("energy")
                        if energy and energy.get("usage"):
                            usage = energy.get("usage")
                            poe = usage.get("total", 0)
                            if poe > 0.0:
                                active_poe_ports[port_id] = {}

                if serial in data:
                    data[serial]["active_poe_ports"] = active_poe_ports

                # Get neighbor info and update port details if available
                neighbors = await _get_neighbors(serial)
                if neighbors:
                    neighbor_ports = neighbors.get("ports") or {}
                    for port_id in active_poe_ports:
                        if port_id in neighbor_ports:
                            active_poe_ports[port_id] = neighbor_ports[port_id].get(
                                "lldp"
                            )

                # Dispatch a signal for each discovered active PoE port only if it's new.
                from .switch import MerakiPoeSwitch

                for port_id in active_poe_ports:
                    unique_id = f"{serial}_poe_port_{port_id}"
                    if unique_id not in dispatched_ports:
                        dispatched_ports.add(unique_id)
                        async_dispatcher_send(
                            hass,
                            f"{DOMAIN}_new_poe_port",
                            MerakiPoeSwitch(coordinator, serial, {"port": port_id}),
                        )

            # Optional: Get active clients and assign them to devices that support clients.
            for network in networks:
                clients = await hass.async_add_executor_job(
                    functools.partial(
                        dashboard.networks.getNetworkClients,
                        network["id"],
                        perPage=5000,
                    )
                )

                for client in clients:
                    if client.get("status") != "Online":
                        continue
                    serial = client.get("recentDeviceSerial")
                    client_id = client.get("id")
                    if serial in data:
                        data[serial]["client_count"] += 1
                        data[serial]["clients"][client_id] = client
                        port = client.get("switchport")
                        if port in data[serial]["active_poe_ports"]:
                            data[serial]["active_poe_ports"][port] = client

        except Exception as e:  # noqa: BLE001
            _LOGGER.error(f"Error updating Meraki data: {e}")  # noqa: G004
        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="meraki_coordinator",
        update_method=async_update_data,
        update_interval=timedelta(seconds=15),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["coordinator"] = coordinator
    hass.data[DOMAIN]["config_entry"] = entry

    # Forward setup to sensor and switch platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    await hass.config_entries.async_forward_entry_setups(entry, ["switch"])

    return True
