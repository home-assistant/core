"""Common device classes for the Actron Air Neo integration."""

from .const import DOMAIN

UNKNOWN_STATUS = "Unknown"


class ACUnit:
    """Representation of an Actron Neo Air Conditioner device."""

    def __init__(self, serial_number, system, status) -> None:
        """Initialize the air conditioner device."""
        self._serial_number = serial_number
        self._status = status
        self._manufacturer = "Actron Air"
        self._name = system["_embedded"]["ac-system"][0]["description"]
        self._firmware_version = self._status.get("AirconSystem", {}).get(
            "MasterWCFirmwareVersion", UNKNOWN_STATUS
        )
        self._model_name = self._status.get("AirconSystem", {}).get(
            "MasterWCModel", UNKNOWN_STATUS
        )

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._serial_number)},
            "name": self._name,
            "manufacturer": self._manufacturer,
            "model": self._model_name,
            "sw_version": self._firmware_version,
            "serial_number": self._serial_number,
        }

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{DOMAIN}_{self._serial_number}"

    @property
    def manufacturer(self) -> str:
        """Return the manufacturer name."""
        return self._manufacturer


class ACZone:
    """Representation of an Air Conditioner Zone."""

    def __init__(self, ac_unit, zone_number, name) -> None:
        """Initialize the zone device."""
        self._ac_unit = ac_unit
        self._zone_number = zone_number
        self._serial = f"zone_{self._zone_number}"
        self._device_type = "Zone"
        self._name = f"Zone {name}"

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._zone_number)},
            "name": self._name,
            "manufacturer": self._ac_unit.manufacturer,
            "model": self._device_type,
        }

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        ac_unit_entity_id = self._ac_unit.unique_id
        return f"{ac_unit_entity_id}_{self._name.replace(' ', '_').lower()}"

    @property
    def zone_number(self) -> int:
        """Return the zone number."""
        return self._zone_number


class ZonePeripheral:
    """Representation of an Actron Air Zone Peripheral."""

    def __init__(
        self,
        ac_unit,
        logical_address,
        serial,
        mac_address,
        zone_assignment,
        device_type,
        software_version,
    ) -> None:
        """Initialize the zone device."""
        self._ac_unit = ac_unit
        self._logical_address = logical_address
        self._serial = serial
        self._mac_address = mac_address
        self._zone_assignment = zone_assignment
        self._device_type = device_type
        self._software_version = software_version
        self._name = f"{self._device_type} {self._logical_address}"

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._serial)},
            "name": self._name,
            "manufacturer": self._ac_unit.manufacturer,
            "model": self._device_type,
            "connections": {("mac", self._mac_address)},  # MAC address
            "serial_number": self._serial,
            "sw_version": self._software_version,
            "via_device": (DOMAIN, self._zone_assignment),
        }

    def logical_address(self) -> str:
        """Return the logical address."""
        return self._logical_address

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        ac_unit_entity_id = self._ac_unit.unique_id
        return f"{ac_unit_entity_id}_{self._name.replace(' ', '_').lower()}"
