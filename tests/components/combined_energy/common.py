"""Common mocks for testing."""
from combined_energy import models


def mock_device(
    device_type: models.DeviceType, *, device_id: int = 13
) -> models.Device:
    """Generate a mock device."""
    return models.Device(
        deviceId=device_id,
        refName="my_device",
        displayName="My Device",
        deviceType=device_type,
        deviceManufacturer="Test Manufacturer",
        deviceModelName="Test Model",
        supplierDevice=True,
        storageDevice=False,
        consumerDevice=False,
        status="OK",
        category="Generic",
    )
