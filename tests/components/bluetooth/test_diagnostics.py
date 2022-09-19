"""Test bluetooth diagnostics."""


from unittest.mock import ANY, patch

from bleak.backends.scanner import BLEDevice

from homeassistant.components import bluetooth

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(
    hass, hass_client, mock_bleak_scanner_start, enable_bluetooth, two_adapters
):
    """Test we can setup and unsetup bluetooth with multiple adapters."""
    # Normally we do not want to patch our classes, but since bleak will import
    # a different scanner based on the operating system, we need to patch here
    # because we cannot import the scanner class directly without it throwing an
    # error if the test is not running on linux since we won't have the correct
    # deps installed when testing on MacOS.
    with patch(
        "homeassistant.components.bluetooth.scanner.HaScanner.discovered_devices",
        [BLEDevice(name="x", rssi=-60, address="44:44:33:11:23:45")],
    ), patch(
        "homeassistant.components.bluetooth.diagnostics.platform.system",
        return_value="Linux",
    ), patch(
        "homeassistant.components.bluetooth.diagnostics.get_dbus_managed_objects",
        return_value={
            "org.bluez": {
                "/org/bluez/hci0": {
                    "org.bluez.Adapter1": {
                        "Name": "BlueZ 5.63",
                        "Alias": "BlueZ 5.63",
                        "Modalias": "usb:v1D6Bp0246d0540",
                        "Discovering": False,
                    },
                    "org.bluez.AdvertisementMonitorManager1": {
                        "SupportedMonitorTypes": ["or_patterns"],
                        "SupportedFeatures": [],
                    },
                }
            }
        },
    ):
        entry1 = MockConfigEntry(
            domain=bluetooth.DOMAIN, data={}, unique_id="00:00:00:00:00:01"
        )
        entry1.add_to_hass(hass)

        entry2 = MockConfigEntry(
            domain=bluetooth.DOMAIN, data={}, unique_id="00:00:00:00:00:02"
        )
        entry2.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry1.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()

        diag = await get_diagnostics_for_config_entry(hass, hass_client, entry1)
        assert diag == {
            "adapters": {
                "hci0": {
                    "address": "00:00:00:00:00:01",
                    "hw_version": "usbid:1234",
                    "passive_scan": False,
                    "sw_version": "BlueZ 4.63",
                },
                "hci1": {
                    "address": "00:00:00:00:00:02",
                    "hw_version": "usbid:1234",
                    "passive_scan": True,
                    "sw_version": "BlueZ 4.63",
                },
            },
            "dbus": {
                "org.bluez": {
                    "/org/bluez/hci0": {
                        "org.bluez.Adapter1": {
                            "Alias": "BlueZ " "5.63",
                            "Discovering": False,
                            "Modalias": "usb:v1D6Bp0246d0540",
                            "Name": "BlueZ " "5.63",
                        },
                        "org.bluez.AdvertisementMonitorManager1": {
                            "SupportedFeatures": [],
                            "SupportedMonitorTypes": ["or_patterns"],
                        },
                    }
                }
            },
            "manager": {
                "adapters": {
                    "hci0": {
                        "address": "00:00:00:00:00:01",
                        "hw_version": "usbid:1234",
                        "passive_scan": False,
                        "sw_version": "BlueZ 4.63",
                    },
                    "hci1": {
                        "address": "00:00:00:00:00:02",
                        "hw_version": "usbid:1234",
                        "passive_scan": True,
                        "sw_version": "BlueZ 4.63",
                    },
                },
                "connectable_history": [],
                "history": [],
                "scanners": [
                    {
                        "adapter": "hci0",
                        "discovered_devices": [
                            {"address": "44:44:33:11:23:45", "name": "x", "rssi": -60}
                        ],
                        "last_detection": ANY,
                        "name": "hci0 (00:00:00:00:00:01)",
                        "source": "hci0",
                        "start_time": ANY,
                        "type": "HaScanner",
                    },
                    {
                        "adapter": "hci0",
                        "discovered_devices": [
                            {"address": "44:44:33:11:23:45", "name": "x", "rssi": -60}
                        ],
                        "last_detection": ANY,
                        "name": "hci0 (00:00:00:00:00:01)",
                        "source": "hci0",
                        "start_time": ANY,
                        "type": "HaScanner",
                    },
                    {
                        "adapter": "hci1",
                        "discovered_devices": [
                            {"address": "44:44:33:11:23:45", "name": "x", "rssi": -60}
                        ],
                        "last_detection": ANY,
                        "name": "hci1 (00:00:00:00:00:02)",
                        "source": "hci1",
                        "start_time": ANY,
                        "type": "HaScanner",
                    },
                ],
            },
        }
