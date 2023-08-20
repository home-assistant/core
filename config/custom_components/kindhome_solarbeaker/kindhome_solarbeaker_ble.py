from homeassistant.components.bluetooth import BluetoothServiceInfoBleak


class KindhomeBluetoothDeviceData:
    def supported(self, data: BluetoothServiceInfoBleak) -> bool:
        pass

    def get_device_name(self) -> str:
        pass
