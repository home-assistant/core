"""This file contains base classes that define Papouch devices."""

from abc import ABC, abstractmethod
from typing import Any


class PapouchDevice(ABC):
    """Abstract class for Papouch devices."""

    name: str = ""
    manufacturer: str = ""
    device_identifiers: dict = {()}

    @abstractmethod
    def parse_xml(self, xml_data: str) -> dict:
        """Parse the device-specific XML and return normalized data.

        The returned dictionary must map the parsed data to standard keys,
        with each containing a nested dictionary indexed by the string `item_id`:

        tag         |  key
        -----------------------------
        temp, sns   -> temperature
        din         -> input
        din_cnt     -> counter
        dout        -> switch

        Example output:
        {
            "temperature": {"1": 25.4, "2": 26.1},
            "switch": {"1": 1, "2": 0}
        }

        If a specific data type is not present on the device, its key should map to an empty dictionary.
        """

    @abstractmethod
    def get_supported_buttons(self) -> list[dict[str, Any]]:
        """Return the configuration data for buttons.

        Expected dictionary structure:
        {
            "name": str,
            "cmd": str
        }
        """

    @abstractmethod
    def get_supported_binary_sensors(self) -> list[dict[str, Any]]:
        """Return the configuration data for binary sensors.

        Expected dictionary structure:
        {
            "item_id": str,
            "type": str,
            "name": str,
            "device_class": str  (Optional)
        }
        """

    @abstractmethod
    def get_supported_numbers(self) -> list[dict[str, Any]]:
        """Return the configuration data for number inputs.

        Expected dictionary structure:
        {
            "item_id": str,
            "category": str,
            "type": str,
            "name": str,
            "min_value": float | int,
            "max_value": float | int,
            "step": float | int,
            "unit": str  (Optional)
        }
        """

    @abstractmethod
    def get_supported_sensors(self) -> list[dict[str, Any]]:
        """Return the configuration data for read-only sensors.

        Expected dictionary structure:
        {
            "item_id": str,
            "type": str,
            "name": str,
            "device_class": str  (Optional),
            "state_class": str  (Optional),
            "unit": str  (Optional)
        }
        """

    @abstractmethod
    def get_supported_switches(self) -> list[dict[str, Any]]:
        """Return the configuration data for switches.

        Expected dictionary structure:
        {
            "item_id": str,
            "name": str
        }
        """

    @abstractmethod
    def get_supported_selects(self) -> list[dict[str, Any]]:
        """Return the configuration data for select menus.

        Expected dictionary structure:
        {
            "item_id": str,
            "category": str,
            "name": str,
            "options": list[str]
        }
        """

    @abstractmethod
    async def execute_button_command(self, cmd_type: str) -> None:
        """Execute the command of the button. Router pattern."""

    @abstractmethod
    async def turn_on_switch(self, item_id: str) -> None:
        """Turn on the switch by its id. Router pattern."""

    @abstractmethod
    async def turn_off_switch(self, item_id: str) -> None:
        """Turn off the switch by its id. Router pattern."""

    @abstractmethod
    async def set_number_value(self, category: str, item_id: str, value: float) -> None:
        """Set the number value by its category and id. Router pattern."""

    @abstractmethod
    def get_select_option(self, category: str, item_id: str) -> str | None:
        """Get the selected option by its category and id. Router pattern."""

    @abstractmethod
    async def set_select_option(self, category: str, item_id: str, option: str) -> None:
        """Set the selected option by its category and id. Router pattern."""

    @abstractmethod
    async def switch_to_web_mode(self) -> None:
        """Switch the device network mode to WEB."""

    @abstractmethod
    def _parse_initial_settings(self) -> None:
        """Parse settings XML for each device.

        Note that this is called only in ctor of the proper device
        and should be a private method.
        """
