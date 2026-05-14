from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MertikConfigEntry
from .coordinator import MertikDataCoordinator
from .entity import MertikEntity

PARALLEL_UPDATES = 0  # read-only coordinator-driven platform

# Maps the raw fault code integer to a translation key.
# Keys must match the state translation keys in strings.json.
FAULT_CODE_MAP: dict[int, str] = {
    2: "f02",
    3: "f03",
    4: "f04",
    6: "f06",
    10: "f10",
    12: "f12",
    13: "f13",
    14: "f14",
    15: "f15",
    16: "f16",
    17: "f17",
    19: "f19",
    26: "f26",
    28: "f28",
    31: "f31",
    41: "f41",
    43: "f43",
    44: "f44",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MertikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    dataservice = entry.runtime_data
    async_add_entities(
        [
            MertikAmbientTemperatureSensorEntity(
                dataservice, entry.entry_id, entry.data["name"]
            ),
            MertikFaultCodeSensorEntity(
                dataservice, entry.entry_id, entry.data["name"]
            ),
        ]
    )


class MertikAmbientTemperatureSensorEntity(MertikEntity, SensorEntity):
    _attr_translation_key = "handset_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, dataservice: MertikDataCoordinator, entry_id: str, device_name: str
    ) -> None:
        super().__init__(dataservice, entry_id, device_name)
        self._attr_unique_id = entry_id + "-AmbientTemperature"

    @property
    def native_value(self) -> float:
        return self._dataservice.ambient_temperature


class MertikFaultCodeSensorEntity(MertikEntity, SensorEntity):
    _attr_translation_key = "fault_code"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = ["none"] + list(FAULT_CODE_MAP.values())

    def __init__(
        self, dataservice: MertikDataCoordinator, entry_id: str, device_name: str
    ) -> None:
        super().__init__(dataservice, entry_id, device_name)
        self._attr_unique_id = entry_id + "-FaultCode"

    @property
    def native_value(self) -> str:
        return FAULT_CODE_MAP.get(self._dataservice.fault_code, "none")
