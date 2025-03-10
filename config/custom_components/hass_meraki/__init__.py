from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import logging
import meraki
from datetime import timedelta
import functools

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

    async def async_update_data():
        """Fetch latest device data and (optionally) active client counts for supported devices."""
        data = {}
        try:
            # Bestimme, welche Netzwerke abgefragt werden
            if network_id:
                networks = [{"id": network_id}]
            elif org_id:
                networks = await hass.async_add_executor_job(
                    dashboard.organizations.getOrganizationNetworks, org_id
                )
            else:
                orgs = await hass.async_add_executor_job(
                    dashboard.organizations.getOrganizations
                )
                networks = []
                for org in orgs:
                    org_networks = await hass.async_add_executor_job(
                        dashboard.organizations.getOrganizationNetworks, org["id"]
                    )
                    networks.extend(org_networks)

            # Hole alle Geräte aus der Organisation(en)
            if org_id:
                all_devices = await hass.async_add_executor_job(
                    dashboard.organizations.getOrganizationDevices, org_id
                )

                # Verfügbarkeitsinformationen für diese Org
                devices_availabilities = await hass.async_add_executor_job(
                    dashboard.organizations.getOrganizationDevicesAvailabilities,
                    org_id,
                )
            else:
                all_devices = []
                devices_availabilities = []
                for org in orgs:
                    org_devices = await hass.async_add_executor_job(
                        dashboard.organizations.getOrganizationDevices, org["id"]
                    )
                    all_devices.extend(org_devices)

                    org_devices_avail = await hass.async_add_executor_job(
                        dashboard.organizations.getOrganizationDevicesAvailabilities,
                        org["id"],
                    )
                    devices_availabilities.extend(org_devices_avail)

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
                    "client_count": 0,  # Standardwert
                    "state": status,  # Verknüpfter Status aus getOrganizationDevicesAvailabilities
                }

            # Optionale Abfrage: Hole aktive Clients und ordne diese Geräten zu,
            # aber nur für Geräte, die auch Clients unterstützen (z.B. Switches, APs, Appliances)
            for network in networks:
                # total_pages='all' überschreibt das Default-Limit
                clients = await hass.async_add_executor_job(
                    functools.partial(
                        dashboard.networks.getNetworkClients,
                        network["id"],
                        total_pages="all",
                    )
                )
                # Gruppiere Clients nach recentDeviceSerial
                device_client_counts = {}
                for client in clients:
                    if client.get("status") != "Online":
                        continue
                    serial = client.get("recentDeviceSerial")
                    if serial:
                        device_client_counts[serial] = (
                            device_client_counts.get(serial, 0) + 1
                        )
                # Aktualisiere für Geräte, die Client-Daten unterstützen (z. B. anhand des productType)
                for serial, count in device_client_counts.items():
                    # Hier könntest du zusätzlich filtern, z.B.:
                    # if data[serial]["productType"] in ["switch", "access point", "appliance"]:
                    if serial in data:
                        data[serial]["client_count"] = count

        except Exception as e:
            _LOGGER.error(f"Error updating Meraki data: {e}")
        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="meraki_coordinator",
        update_method=async_update_data,
        update_interval=timedelta(minutes=5),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["coordinator"] = coordinator
    hass.data[DOMAIN]["config_entry"] = entry

    # Starte die Sensor-Plattform (die Sensoren für z. B. Client Counts erzeugt)
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True
