"""This file contains base classes that define Papouch devices."""

from abc import ABC, abstractmethod


class PapouchDevice(ABC):
    """Abstract class for Papouch devices."""

    name: str = ""
    manufacturer: str = ""
    device_identifiers: dict = {()}

    @abstractmethod
    def parse_xml(self, xml_data: str) -> dict:
        """Abstract method for parsing XML for each device."""

    @abstractmethod
    def get_supported_buttons(self) -> list[dict[str, str]]:
        """Return the configuration data for buttons."""

    @abstractmethod
    def get_supported_binary_sensors(self) -> list[dict[str, str]]:
        """Return the configuration data for binary sensors."""

    @abstractmethod
    def get_supported_numbers(self) -> list[dict[str, str]]:
        """Return the configuration data for number inputs (decreasing counters) that supports Quido."""

    @abstractmethod
    def get_supported_sensors(self) -> list[dict[str, str]]:
        """Return the configuration data for read-only sensors (temperatures and counters) this device supports."""

    @abstractmethod
    def get_supported_switches(self) -> list[dict[str, str]]:
        """Return the configuration data for switches (outputs) this device supports."""
