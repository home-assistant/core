"""The Cisco Meraki Integration."""

from datetime import timedelta
import functools
import logging

import meraki

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
        """Call the Meraki API to change the PoE state for this port."""
        try:
            return await hass.async_add_executor_job(
                dashboard.devices.getDeviceLldpCdp, serial
            )
        except meraki.APIError as err:
            _LOGGER.error("Failed to get neighbors for serial %s: %s", serial, err)
            return False

    async def async_update_data():
        """Fetch latest device data and (optionally) active client counts for supported devices."""
        data = {}
        try:
            # Bestimme, welche Netzwerke abgefragt werden
            if network_id:
                networks = [{"id": network_id}]
            else:
                networks = await hass.async_add_executor_job(
                    dashboard.organizations.getOrganizationNetworks, org_id
                )

            # Hole alle Geräte aus der Organisation
            all_devices = await hass.async_add_executor_job(
                dashboard.organizations.getOrganizationDevices, org_id
            )

            # Verfügbarkeitsinformationen für diese Org
            devices_availabilities = await hass.async_add_executor_job(
                dashboard.organizations.getOrganizationDevicesAvailabilities,
                org_id,
            )

            # Port Informationen für diese Org
            port_usage = await hass.async_add_executor_job(
                functools.partial(
                    dashboard.switch.getOrganizationSwitchPortsUsageHistoryByDeviceByInterval,
                    org_id,
                    timespan=900,
                )
            )

            # Falls eine Network ID angegeben wurde, filtern wir die Geräte nach Netzwerk
            if network_id:
                all_devices = [
                    device
                    for device in all_devices
                    if device.get("networkId") == network_id
                ]

            # Lege ein Dictionary an, um Availability-Einträge anhand der Seriennummer abzugleichen
            avail_map = {item["serial"]: item for item in devices_availabilities}

            # Speichere die statischen Geräteeigenschaften in data
            for device in all_devices:
                serial = device.get("serial")
                if not serial:
                    continue

                # Availability-Infos für diese Seriennummer heraussuchen
                device_avail = avail_map.get(serial, {})
                # Hier wird angenommen, dass device_avail["status"] existiert.
                # Falls es einen anderen Key gibt (z. B. "availability"), passe das entsprechend an.
                status = device_avail.get("status", "Unknown")

                data[serial] = {
                    "name": device.get("name", f"Meraki Device {serial}"),
                    "model": device.get("model", "Unknown"),
                    "firmware": device.get("firmware", "Unknown"),
                    "mac": device.get("mac", "Unknown"),
                    "networkId": device.get("networkId"),
                    "serial": serial,
                    "productType": device.get("productType", None),  # falls vorhanden
                    "state": status,  # Verknüpfter Status aus getOrganizationDevicesAvailabilities
                    "client_count": 0,
                    "clients": {},
                    "active_poe_ports": [],
                }

            port_usage = port_usage.get("items")

            if network_id:
                port_usage = [
                    switch
                    for switch in port_usage
                    if switch.get("networkId") == network_id
                ]

            for switch in port_usage:
                serial = switch.get("serial")
                if not serial:
                    continue

                active_poe_ports = {}

                ports = switch.get("ports")
                for port in ports:
                    port_id = port.get("portId")

                    if port.get("intervals")[0]["energy"]["usage"]:
                        poe = port.get("intervals")[0]["energy"]["usage"]["total"]
                        if poe > 0.0:
                            poe_port = {}
                            active_poe_ports[port_id] = poe_port

                if serial in data:
                    data[serial]["active_poe_ports"] = active_poe_ports

                neighbors = await _get_neighbors(serial)
                ports = neighbors.get("ports")
                for port in ports:
                    if port in active_poe_ports:
                        active_poe_ports[port] = neighbors["ports"][port]["lldp"]
            # Optionale Abfrage: Hole aktive Clients und ordne diese Geräten zu,
            # aber nur für Geräte, die auch Clients unterstützen (z.B. Switches, APs, Appliances)
            for network in networks:
                # total_pages='all' überschreibt das Default-Limit
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
                        if port in active_poe_ports:
                            active_poe_ports[port] = client

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

    # Starte die Sensor-Plattform (die Sensoren für z. B. Client Counts erzeugt)
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    await hass.config_entries.async_forward_entry_setups(entry, ["switch"])

    return True
