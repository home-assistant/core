"""Discovery helpers for Mitsubishi Comfort Cloud."""

from mitsubishi_comfort import DeviceInfo, MitsubishiCloudAccount


async def async_discover_devices(
    account: MitsubishiCloudAccount,
) -> dict[str, DeviceInfo]:
    """Discover indoor units without retrieving local-control credentials."""
    devices: dict[str, DeviceInfo] = {}
    for site in await account.get_sites():
        if not (site_id := site.get("id")):
            continue
        for zone in await account.get_zones(site_id):
            adapter = zone.get("adapter", {})
            if adapter.get("isHeadless") or not (serial := adapter.get("deviceSerial")):
                continue
            devices[serial] = DeviceInfo(
                serial=serial,
                label=zone.get("name", ""),
                site_id=site_id,
                unit_type="ductless",
                address="",
                mac="",
                password="",
                crypto_serial="",
            )
    return devices
