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

    async def _get_ports(serial):
        """Call the Meraki API to change the PoE state for this port."""
        try:
            return await hass.async_add_executor_job(
                functools.partial(
                    dashboard.switch.getDeviceSwitchPortsStatuses,
                    serial,
                    timespan=300,
                )
            )
        except meraki.APIError as err:
            _LOGGER.error("Failed to get ports for serial %s: %s", serial, err)
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

            all_devices = await hass.async_add_executor_job(
                dashboard.organizations.getOrganizationDevices, org_id
            )

            # Verfügbarkeitsinformationen für diese Org
            devices_availabilities = await hass.async_add_executor_job(
                dashboard.organizations.getOrganizationDevicesAvailabilities,
                org_id,
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
                    "ports": {},
                }

                if device.get("productType") == "switch":
                    ports = await _get_ports(serial)
                    data[serial]["ports"] = ports

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
