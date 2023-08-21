from homeassistant.components.bluetooth import BluetoothServiceInfoBleak


class KindhomeBluetoothDeviceData:
    def supported(self, data: BluetoothServiceInfoBleak) -> bool:
        return True

    def get_device_name(self) -> str:
        return "Markiza"
