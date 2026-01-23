---
title: "Fetching Bluetooth data"
---

## Choosing a method to fetch data

If the device's primary method to notify of updates is Bluetooth advertisements and its primary function is a sensor, binary sensor, or firing events:

- If all sensors are updated via Bluetooth advertisements: [`PassiveBluetoothProcessorCoordinator`](#passivebluetoothprocessorcoordinator)
- If active connection are needed for some sensors: [`ActiveBluetoothProcessorCoordinator`](#activebluetoothprocessorcoordinator)

If the device's primary method to notify of updates is Bluetooth advertisements and its primary function is **not** a sensor, binary sensor, or firing events:

- If all entities are updated via Bluetooth advertisements: [`PassiveBluetoothCoordinator`](#passivebluetoothcoordinator)
- If active connections are needed: [`ActiveBluetoothCoordinator`](#activebluetoothcoordinator)

If your device only communicates with an active Bluetooth connection and does not use Bluetooth advertisements:

- [`DataUpdateCoordinator`](/docs/integration_fetching_data)

## BluetoothProcessorCoordinator

The `ActiveBluetoothProcessorCoordinator` and `PassiveBluetoothProcessorCoordinator` significantly reduce the code needed for creating integrations that primary function as sensor, binary sensors, or fire events. By formatting the data fed into the processor coordinators into a `PassiveBluetoothDataUpdate` object, the
frameworks can take care of creating the entities on demand and allow for minimal `sensor` and `binary_sensor` platform implementations.

These frameworks require the data coming from the library to be formatted into a `PassiveBluetoothDataUpdate` as shown below:

```python
@dataclasses.dataclass(frozen=True)
class PassiveBluetoothEntityKey:
    """Key for a passive bluetooth entity.

    Example:
    key: temperature
    device_id: outdoor_sensor_1
    """

    key: str
    device_id: str | None

@dataclasses.dataclass(frozen=True)
class PassiveBluetoothDataUpdate(Generic[_T]):
    """Generic bluetooth data."""

    devices: dict[str | None, DeviceInfo] = dataclasses.field(default_factory=dict)
    entity_descriptions: Mapping[
        PassiveBluetoothEntityKey, EntityDescription
    ] = dataclasses.field(default_factory=dict)
    entity_names: Mapping[PassiveBluetoothEntityKey, str | None] = dataclasses.field(
        default_factory=dict
    )
    entity_data: Mapping[PassiveBluetoothEntityKey, _T] = dataclasses.field(
        default_factory=dict
    )
```

### PassiveBluetoothProcessorCoordinator

Example `async_setup_entry` for an integration `__init__.py` using a `PassiveBluetoothProcessorCoordinator`:

```python
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from .const import DOMAIN
from homeassistant.const import Platform

PLATFORMS: list[Platform] = [Platform.SENSOR]

from your_library import DataParser

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up example BLE device from a config entry."""
    address = entry.unique_id
    data = DataParser()
    coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.ACTIVE,
        update_method=data.update,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(
        # only start after all platforms have had a chance to subscribe
        coordinator.async_start()
    )
    return True
```

Example `sensor.py`:

```python
from homeassistant import config_entries
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


def sensor_update_to_bluetooth_data_update(parsed_data):
    """Convert a sensor update to a Bluetooth data update."""
    # This function must convert the parsed_data
    # from your library's update_method to a `PassiveBluetoothDataUpdate`
    # See the structure above
    return PassiveBluetoothDataUpdate(
        devices={},
        entity_descriptions={},
        entity_data={},
        entity_names={},
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the example BLE sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            ExampleBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class ExampleBluetoothSensorEntity(PassiveBluetoothProcessorEntity, SensorEntity):
    """Representation of an example BLE sensor."""

    @property
    def native_value(self) -> float | int | str | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)

```

### ActiveBluetoothProcessorCoordinator

An `ActiveBluetoothProcessorCoordinator` functions nearly the same as a `PassiveBluetoothProcessorCoordinator`
but will also make an active connection to poll for data based on `needs_poll_method` and a `poll_method`
function which are called when the device's Bluetooth advertisement changes. The `sensor.py` implementation
is the same as the `PassiveBluetoothProcessorCoordinator`.

Example `async_setup_entry` for an integration `__init__.py` using an `ActiveBluetoothProcessorCoordinator`:

```python
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.components.bluetooth import BluetoothScanningMode

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.const import Platform

from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
PLATFORMS: list[Platform] = [Platform.SENSOR]

from your_library import DataParser

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up example BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    data = DataParser()

    def _needs_poll(
        service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        return (
            hass.state == CoreState.running
            and data.poll_needed(service_info, last_poll)
            and bool(
                async_ble_device_from_address(
                    hass, service_info.device.address, connectable=True
                )
            )
        )

    async def _async_poll(service_info: BluetoothServiceInfoBleak):
        if service_info.connectable:
            connectable_device = service_info.device
        elif device := async_ble_device_from_address(
            hass, service_info.device.address, True
        ):
            connectable_device = device
        else:
            # We have no Bluetooth controller that is in range of
            # the device to poll it
            raise RuntimeError(
                f"No connectable device found for {service_info.device.address}"
            )
        return await data.async_poll(connectable_device)

    coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = ActiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=data.update,
        needs_poll_method=_needs_poll,
        poll_method=_async_poll,
        # We will take advertisements from non-connectable devices
        # since we will trade the BLEDevice for a connectable one
        # if we need to poll it
        connectable=False,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(
        # only start after all platforms have had a chance to subscribe
        coordinator.async_start()
    )
    return True
```

## BluetoothCoordinator

The `ActiveBluetoothCoordinator` and `PassiveBluetoothCoordinator` coordinators function similar
to `DataUpdateCoordinators` except they are driven by incoming advertisement data instead of polling.

### PassiveBluetoothCoordinator

Below is an example of a `PassiveBluetoothDataUpdateCoordinator`. Incoming
data is received via `_async_handle_bluetooth_event` and processed by the integration's
library.

```python
import logging
from typing import TYPE_CHECKING

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.active_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import CoreState, HomeAssistant, callback

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice


class ExamplePassiveBluetoothDataUpdateCoordinator(
    PassiveBluetoothDataUpdateCoordinator[None]
):
    """Class to manage fetching example data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        ble_device: BLEDevice,
        device: YourLibDevice,
    ) -> None:
        """Initialize example data coordinator."""
        super().__init__(
            hass=hass,
            logger=logger,
            address=ble_device.address,
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=False,
        )
        self.device = device

    @callback
    def _async_handle_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Handle the device going unavailable."""

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        # Your device should process incoming advertisement data

```

### ActiveBluetoothCoordinator

Below is an example of an `ActiveBluetoothDataUpdateCoordinator`. Incoming data is received via `_async_handle_bluetooth_event` and processed by the integration's library.

The method passed to `needs_poll_method` is called each time the Bluetooth advertisement changes to determine if the method passed to `poll_method` should be called to make an active connection to the device to obtain additional data.

```python
import logging
from typing import TYPE_CHECKING

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import CoreState, HomeAssistant, callback

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice


class ExampleActiveBluetoothDataUpdateCoordinator(
    ActiveBluetoothDataUpdateCoordinator[None]
):
    """Class to manage fetching example data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        ble_device: BLEDevice,
        device: YourLibDevice,
    ) -> None:
        """Initialize example data coordinator."""
        super().__init__(
            hass=hass,
            logger=logger,
            address=ble_device.address,
            needs_poll_method=self._needs_poll,
            poll_method=self._async_update,
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=True,
        )
        self.device = device

    @callback
    def _needs_poll(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        seconds_since_last_poll: float | None,
    ) -> bool:
        # Only poll if hass is running, we need to poll,
        # and we actually have a way to connect to the device
        return (
            self.hass.state == CoreState.running
            and self.device.poll_needed(seconds_since_last_poll)
            and bool(
                bluetooth.async_ble_device_from_address(
                    self.hass, service_info.device.address, connectable=True
                )
            )
        )

    async def _async_update(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Poll the device."""

    @callback
    def _async_handle_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Handle the device going unavailable."""

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        # Your device should process incoming advertisement data

```
