"""Test bluetooth diagnostics."""

from unittest.mock import ANY, MagicMock, patch

from bleak.backends.scanner import AdvertisementData, BLEDevice
from bluetooth_adapters import DEFAULT_ADDRESS

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    MONOTONIC_TIME,
    BaseHaRemoteScanner,
    HaBluetoothConnector,
    HaScanner,
)
from homeassistant.core import HomeAssistant

from . import (
    FakeScannerMixin,
    MockBleakClient,
    _get_manager,
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement,
)

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


class FakeHaScanner(FakeScannerMixin, HaScanner):
    """Fake HaScanner."""

    @property
    def discovered_devices_and_advertisement_data(self):
        """Return the discovered devices and advertisement data."""
        return {
            "44:44:33:11:23:45": (
                generate_ble_device(name="x", rssi=-127, address="44:44:33:11:23:45"),
                generate_advertisement_data(local_name="x"),
            )
        }


@patch("homeassistant.components.bluetooth.HaScanner", FakeHaScanner)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bleak_scanner_start: MagicMock,
    enable_bluetooth: None,
    two_adapters: None,
) -> None:
    """Test we can setup and unsetup bluetooth with multiple adapters."""
    # Normally we do not want to patch our classes, but since bleak will import
    # a different scanner based on the operating system, we need to patch here
    # because we cannot import the scanner class directly without it throwing an
    # error if the test is not running on linux since we won't have the correct
    # deps installed when testing on MacOS.

    with (
        patch(
            "homeassistant.components.bluetooth.diagnostics.platform.system",
            return_value="Linux",
        ),
        patch(
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
        ),
    ):
        entry2 = MockConfigEntry(
            domain=bluetooth.DOMAIN, data={}, unique_id="00:00:00:00:00:02"
        )
        entry2.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()

        diag = await get_diagnostics_for_config_entry(hass, hass_client, entry2)
        expected = {
            "adapters": {
                "hci0": {
                    "address": "00:00:00:00:00:01",
                    "connection_slots": 1,
                    "hw_version": "usb:v1D6Bp0246d053F",
                    "manufacturer": "ACME",
                    "passive_scan": False,
                    "product": "Bluetooth Adapter 5.0",
                    "product_id": "aa01",
                    "sw_version": ANY,
                    "vendor_id": "cc01",
                },
                "hci1": {
                    "address": "00:00:00:00:00:02",
                    "connection_slots": 2,
                    "hw_version": "usb:v1D6Bp0246d053F",
                    "manufacturer": "ACME",
                    "passive_scan": True,
                    "product": "Bluetooth Adapter 5.0",
                    "product_id": "aa01",
                    "sw_version": ANY,
                    "vendor_id": "cc01",
                },
            },
            "dbus": {
                "org.bluez": {
                    "/org/bluez/hci0": {
                        "org.bluez.Adapter1": {
                            "Alias": "BlueZ 5.63",
                            "Discovering": False,
                            "Modalias": "usb:v1D6Bp0246d0540",
                            "Name": "BlueZ 5.63",
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
                        "connection_slots": 1,
                        "hw_version": "usb:v1D6Bp0246d053F",
                        "manufacturer": "ACME",
                        "passive_scan": False,
                        "product": "Bluetooth Adapter 5.0",
                        "product_id": "aa01",
                        "sw_version": "homeassistant",
                        "vendor_id": "cc01",
                    },
                    "hci1": {
                        "address": "00:00:00:00:00:02",
                        "connection_slots": 2,
                        "hw_version": "usb:v1D6Bp0246d053F",
                        "manufacturer": "ACME",
                        "passive_scan": True,
                        "product": "Bluetooth Adapter 5.0",
                        "product_id": "aa01",
                        "sw_version": "homeassistant",
                        "vendor_id": "cc01",
                    },
                },
                "advertisement_tracker": {
                    "fallback_intervals": {},
                    "intervals": {},
                    "sources": {},
                    "timings": {},
                },
                "all_history": [],
                "connectable_history": [],
                "scanners": [
                    {
                        "adapter": "hci0",
                        "discovered_devices_and_advertisement_data": [],
                        "last_detection": ANY,
                        "monotonic_time": ANY,
                        "name": "hci0 (00:00:00:00:00:01)",
                        "scanning": True,
                        "source": "00:00:00:00:00:01",
                        "start_time": ANY,
                        "type": "HaScanner",
                        "current_mode": {
                            "__type": "<enum 'BluetoothScanningMode'>",
                            "repr": "<BluetoothScanningMode.ACTIVE: 'active'>",
                        },
                        "requested_mode": {
                            "__type": "<enum 'BluetoothScanningMode'>",
                            "repr": "<BluetoothScanningMode.ACTIVE: 'active'>",
                        },
                    },
                    {
                        "adapter": "hci1",
                        "discovered_devices_and_advertisement_data": [
                            {
                                "address": "44:44:33:11:23:45",
                                "advertisement_data": [
                                    "x",
                                    {},
                                    {},
                                    [],
                                    -127,
                                    -127,
                                    [[]],
                                ],
                                "details": None,
                                "name": "x",
                                "rssi": -127,
                            }
                        ],
                        "last_detection": ANY,
                        "monotonic_time": ANY,
                        "name": "hci1 (00:00:00:00:00:02)",
                        "scanning": True,
                        "source": "00:00:00:00:00:02",
                        "start_time": ANY,
                        "type": "FakeHaScanner",
                        "current_mode": {
                            "__type": "<enum 'BluetoothScanningMode'>",
                            "repr": "<BluetoothScanningMode.ACTIVE: 'active'>",
                        },
                        "requested_mode": {
                            "__type": "<enum 'BluetoothScanningMode'>",
                            "repr": "<BluetoothScanningMode.ACTIVE: 'active'>",
                        },
                    },
                ],
                "slot_manager": {
                    "adapter_slots": {"hci0": 5, "hci1": 2},
                    "allocations_by_adapter": {"hci0": [], "hci1": []},
                    "manager": False,
                },
            },
        }
        diag_scanners = diag["manager"].pop("scanners")
        expected_scanners = expected["manager"].pop("scanners")
        assert diag == expected
        assert sorted(diag_scanners, key=lambda x: x["name"]) == sorted(
            expected_scanners, key=lambda x: x["name"]
        )


@patch("homeassistant.components.bluetooth.HaScanner", FakeHaScanner)
async def test_diagnostics_macos(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
    macos_adapter,
) -> None:
    """Test diagnostics for macos."""
    # Normally we do not want to patch our classes, but since bleak will import
    # a different scanner based on the operating system, we need to patch here
    # because we cannot import the scanner class directly without it throwing an
    # error if the test is not running on linux since we won't have the correct
    # deps installed when testing on MacOS.
    switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=[], manufacturer_data={1: b"\x01"}
    )

    with (
        patch(
            "homeassistant.components.bluetooth.diagnostics.platform.system",
            return_value="Darwin",
        ),
        patch(
            "homeassistant.components.bluetooth.diagnostics.get_dbus_managed_objects",
            return_value={},
        ),
    ):
        entry1 = MockConfigEntry(
            domain=bluetooth.DOMAIN,
            data={},
            title="Core Bluetooth",
            unique_id=DEFAULT_ADDRESS,
        )
        entry1.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry1.entry_id)
        await hass.async_block_till_done()

        inject_advertisement(hass, switchbot_device, switchbot_adv)

        diag = await get_diagnostics_for_config_entry(hass, hass_client, entry1)
        assert diag == {
            "adapters": {
                "Core Bluetooth": {
                    "address": "00:00:00:00:00:00",
                    "manufacturer": "Apple",
                    "passive_scan": False,
                    "product": "Unknown MacOS Model",
                    "product_id": "Unknown",
                    "sw_version": ANY,
                    "vendor_id": "Unknown",
                }
            },
            "manager": {
                "adapters": {
                    "Core Bluetooth": {
                        "address": "00:00:00:00:00:00",
                        "manufacturer": "Apple",
                        "passive_scan": False,
                        "product": "Unknown MacOS Model",
                        "product_id": "Unknown",
                        "sw_version": ANY,
                        "vendor_id": "Unknown",
                    }
                },
                "advertisement_tracker": {
                    "fallback_intervals": {},
                    "intervals": {},
                    "sources": {"44:44:33:11:23:45": "local"},
                    "timings": {"44:44:33:11:23:45": [ANY]},
                },
                "all_history": [
                    {
                        "address": "44:44:33:11:23:45",
                        "advertisement": [
                            "wohand",
                            {"1": {"__type": "<class 'bytes'>", "repr": "b'\\x01'"}},
                            {},
                            [],
                            -127,
                            -127,
                            [[]],
                        ],
                        "connectable": True,
                        "device": {
                            "__type": "<class 'bleak.backends.device.BLEDevice'>",
                            "repr": "BLEDevice(44:44:33:11:23:45, wohand)",
                        },
                        "manufacturer_data": {
                            "1": {"__type": "<class 'bytes'>", "repr": "b'\\x01'"}
                        },
                        "name": "wohand",
                        "rssi": -127,
                        "service_data": {},
                        "service_uuids": [],
                        "source": "local",
                        "time": ANY,
                        "tx_power": -127,
                    }
                ],
                "connectable_history": [
                    {
                        "address": "44:44:33:11:23:45",
                        "advertisement": [
                            "wohand",
                            {"1": {"__type": "<class 'bytes'>", "repr": "b'\\x01'"}},
                            {},
                            [],
                            -127,
                            -127,
                            [[]],
                        ],
                        "connectable": True,
                        "device": {
                            "__type": "<class 'bleak.backends.device.BLEDevice'>",
                            "repr": "BLEDevice(44:44:33:11:23:45, wohand)",
                        },
                        "manufacturer_data": {
                            "1": {"__type": "<class 'bytes'>", "repr": "b'\\x01'"}
                        },
                        "name": "wohand",
                        "rssi": -127,
                        "service_data": {},
                        "service_uuids": [],
                        "source": "local",
                        "time": ANY,
                        "tx_power": -127,
                    }
                ],
                "scanners": [
                    {
                        "adapter": "Core Bluetooth",
                        "discovered_devices_and_advertisement_data": [
                            {
                                "address": "44:44:33:11:23:45",
                                "advertisement_data": [
                                    "x",
                                    {},
                                    {},
                                    [],
                                    -127,
                                    -127,
                                    [[]],
                                ],
                                "details": None,
                                "name": "x",
                                "rssi": -127,
                            }
                        ],
                        "last_detection": ANY,
                        "monotonic_time": ANY,
                        "name": "Core Bluetooth",
                        "scanning": True,
                        "source": "Core Bluetooth",
                        "start_time": ANY,
                        "type": "FakeHaScanner",
                        "current_mode": {
                            "__type": "<enum 'BluetoothScanningMode'>",
                            "repr": "<BluetoothScanningMode.ACTIVE: 'active'>",
                        },
                        "requested_mode": {
                            "__type": "<enum 'BluetoothScanningMode'>",
                            "repr": "<BluetoothScanningMode.ACTIVE: 'active'>",
                        },
                    }
                ],
                "slot_manager": {
                    "adapter_slots": {"Core Bluetooth": 5},
                    "allocations_by_adapter": {"Core Bluetooth": []},
                    "manager": False,
                },
            },
        }


@patch("homeassistant.components.bluetooth.HaScanner", FakeHaScanner)
async def test_diagnostics_remote_adapter(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
    enable_bluetooth: None,
    one_adapter: None,
) -> None:
    """Test diagnostics for remote adapter."""
    manager = _get_manager()
    switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=[], manufacturer_data={1: b"\x01"}
    )

    class FakeScanner(BaseHaRemoteScanner):
        def inject_advertisement(
            self, device: BLEDevice, advertisement_data: AdvertisementData
        ) -> None:
            """Inject an advertisement."""
            self._async_on_advertisement(
                device.address,
                advertisement_data.rssi,
                device.name,
                advertisement_data.service_uuids,
                advertisement_data.service_data,
                advertisement_data.manufacturer_data,
                advertisement_data.tx_power,
                {"scanner_specific_data": "test"},
                MONOTONIC_TIME(),
            )

    with (
        patch(
            "homeassistant.components.bluetooth.diagnostics.platform.system",
            return_value="Linux",
        ),
        patch(
            "homeassistant.components.bluetooth.diagnostics.get_dbus_managed_objects",
            return_value={},
        ),
    ):
        entry1 = hass.config_entries.async_entries(bluetooth.DOMAIN)[0]
        connector = (
            HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
        )
        scanner = FakeScanner("esp32", "esp32", connector, True)
        unsetup = scanner.async_setup()
        cancel = manager.async_register_scanner(scanner)

        scanner.inject_advertisement(switchbot_device, switchbot_adv)
        inject_advertisement(hass, switchbot_device, switchbot_adv)

        diag = await get_diagnostics_for_config_entry(hass, hass_client, entry1)

        expected = {
            "adapters": {
                "hci0": {
                    "address": "00:00:00:00:00:01",
                    "hw_version": "usb:v1D6Bp0246d053F",
                    "manufacturer": "ACME",
                    "passive_scan": False,
                    "product": "Bluetooth Adapter 5.0",
                    "product_id": "aa01",
                    "sw_version": ANY,
                    "vendor_id": "cc01",
                }
            },
            "dbus": {},
            "manager": {
                "adapters": {
                    "hci0": {
                        "address": "00:00:00:00:00:01",
                        "hw_version": "usb:v1D6Bp0246d053F",
                        "manufacturer": "ACME",
                        "passive_scan": False,
                        "product": "Bluetooth Adapter 5.0",
                        "product_id": "aa01",
                        "sw_version": ANY,
                        "vendor_id": "cc01",
                    }
                },
                "advertisement_tracker": {
                    "fallback_intervals": {},
                    "intervals": {},
                    "sources": {"44:44:33:11:23:45": "esp32"},
                    "timings": {"44:44:33:11:23:45": [ANY]},
                },
                "all_history": [
                    {
                        "address": "44:44:33:11:23:45",
                        "advertisement": [
                            "wohand",
                            {"1": {"__type": "<class 'bytes'>", "repr": "b'\\x01'"}},
                            {},
                            [],
                            -127,
                            -127,
                            [],
                        ],
                        "connectable": True,
                        "device": {
                            "__type": "<class 'bleak.backends.device.BLEDevice'>",
                            "repr": "BLEDevice(44:44:33:11:23:45, wohand)",
                        },
                        "manufacturer_data": {
                            "1": {"__type": "<class 'bytes'>", "repr": "b'\\x01'"}
                        },
                        "name": "wohand",
                        "rssi": -127,
                        "service_data": {},
                        "service_uuids": [],
                        "source": "esp32",
                        "time": ANY,
                        "tx_power": -127,
                    }
                ],
                "connectable_history": [
                    {
                        "address": "44:44:33:11:23:45",
                        "advertisement": [
                            "wohand",
                            {"1": {"__type": "<class 'bytes'>", "repr": "b'\\x01'"}},
                            {},
                            [],
                            -127,
                            -127,
                            [],
                        ],
                        "connectable": True,
                        "device": {
                            "__type": "<class 'bleak.backends.device.BLEDevice'>",
                            "repr": "BLEDevice(44:44:33:11:23:45, wohand)",
                        },
                        "manufacturer_data": {
                            "1": {"__type": "<class 'bytes'>", "repr": "b'\\x01'"}
                        },
                        "name": "wohand",
                        "rssi": -127,
                        "service_data": {},
                        "service_uuids": [],
                        "source": "esp32",
                        "time": ANY,
                        "tx_power": -127,
                    }
                ],
                "scanners": [
                    {
                        "adapter": "hci0",
                        "discovered_devices_and_advertisement_data": [],
                        "last_detection": ANY,
                        "monotonic_time": ANY,
                        "name": "hci0 (00:00:00:00:00:01)",
                        "scanning": True,
                        "source": "00:00:00:00:00:01",
                        "start_time": ANY,
                        "type": "HaScanner",
                        "current_mode": {
                            "__type": "<enum 'BluetoothScanningMode'>",
                            "repr": "<BluetoothScanningMode.ACTIVE: 'active'>",
                        },
                        "requested_mode": {
                            "__type": "<enum 'BluetoothScanningMode'>",
                            "repr": "<BluetoothScanningMode.ACTIVE: 'active'>",
                        },
                    },
                    {
                        "connectable": True,
                        "discovered_device_timestamps": {"44:44:33:11:23:45": ANY},
                        "discovered_devices_and_advertisement_data": [
                            {
                                "address": "44:44:33:11:23:45",
                                "advertisement_data": [
                                    "wohand",
                                    {
                                        "1": {
                                            "__type": "<class 'bytes'>",
                                            "repr": "b'\\x01'",
                                        }
                                    },
                                    {},
                                    [],
                                    -127,
                                    -127,
                                    [],
                                ],
                                "details": {
                                    "scanner_specific_data": "test",
                                    "source": "esp32",
                                },
                                "name": "wohand",
                                "rssi": -127,
                            }
                        ],
                        "last_detection": ANY,
                        "monotonic_time": ANY,
                        "name": "esp32",
                        "scanning": True,
                        "source": "esp32",
                        "start_time": ANY,
                        "time_since_last_device_detection": {"44:44:33:11:23:45": ANY},
                        "type": "FakeScanner",
                    },
                ],
                "slot_manager": {
                    "adapter_slots": {"hci0": 5},
                    "allocations_by_adapter": {"hci0": []},
                    "manager": False,
                },
            },
        }

        diag_scanners = diag["manager"].pop("scanners")
        expected_scanners = expected["manager"].pop("scanners")
        assert diag == expected
        assert sorted(diag_scanners, key=lambda x: x["name"]) == sorted(
            expected_scanners, key=lambda x: x["name"]
        )

    cancel()
    unsetup()
