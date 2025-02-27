"""Support for Automation Device Specification (ADS).

This module provides a representation for an ADS connection and related utilities.
"""

from collections.abc import Callable, Iterable
import ctypes
from itertools import product
import logging
import re
import struct
import threading
from typing import Any, NamedTuple

import pyads

from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT

from .const import CONF_ADS_FIELDS, CONF_ADS_HUB, CONF_ADS_NAME, AdsDiscoveryKeys

_LOGGER = logging.getLogger(__name__)


class NotificationItem(NamedTuple):
    """Holds data needed for an ADS device notification.

    Attributes:
        hnotify: The notification handle.
        huser: The user handle.
        name: The variable name.
        plc_datatype: The PLC datatype.
        callback: Function to call when a notification is received.

    """

    hnotify: int
    huser: int
    name: str
    plc_datatype: Any  # Specify a more precise type if known
    callback: Callable[[str, Any], None]


class ArrayRegex:
    """Precompiled regex patterns for parsing ADS array declarations.

    Patterns:
      - ARRAY_REGEX:
          Matches a generic array declaration.
          Example: "ARRAY [1..10] OF INT" returns group 1: "INT".

      - COMPACT_ARRAY_REGEX:
          Matches compact multidimensional arrays.
          Example: "ARRAY [1..2, 1..3] OF INT" returns group 1: "1..2, 1..3".

      - NESTED_ARRAY_REGEX:
          Matches nested array declarations.
          Example: "ARRAY [1..5] OF ARRAY [1..10] OF REAL" returns group 1: "1..5" and group 2: "ARRAY [1..10] OF REAL".

    """

    ARRAY_REGEX = re.compile(r"ARRAY\s*\[.*?\]\s*OF\s*(.+)")
    COMPACT_ARRAY_REGEX = re.compile(r"ARRAY\s*\[([\d\.\-,\s]+)\]\s*OF")
    NESTED_ARRAY_REGEX = re.compile(r"ARRAY\s*\[(\d+\.\.\d+)\]\s*OF\s*(.+)")


class AdsHub:
    """Representation of an ADS connection.

    This class encapsulates methods to manage the ADS connection, read/write data,
    handle notifications and process symbols.
    """

    def __init__(self, ads_client: pyads.Connection) -> None:
        """Initialize the ADS hub.

        Args:
            ads_client: The underlying pyads.Connection instance.

        """
        self._client: pyads.Connection = ads_client
        self.connection_params: dict[str, Any] = {}  # Connection parameters

        # List to register all ADS devices.
        self._devices: list[Any] = []
        # Mapping of active notification handles to NotificationItems.
        self._notification_items: dict[int, NotificationItem] = {}
        # Temporary storage for notifications during reinitialization.
        self._temp_notification_items: list[NotificationItem] = []
        self._lock = threading.Lock()

    def reconnect(self) -> None:
        """Restart the ADS connection.

        Attempts to create a new connection using stored parameters.

        """
        hub_name = self.connection_params.get(CONF_ADS_HUB)
        device = self.connection_params.get(CONF_DEVICE)
        ip_address = self.connection_params.get(CONF_IP_ADDRESS)
        port = self.connection_params.get(CONF_PORT)

        _LOGGER.info("[%s] Attempting to restart ADS connection", hub_name)

        try:
            self._client = pyads.Connection(device, port, ip_address)
            self._client.open()
        except pyads.ADSError as err:
            _LOGGER.error("[%s] ADS error during ADS restart: %s", hub_name, err)
        except Exception as e:
            _LOGGER.error("[%s] Unexpected error during ADS restart: %s", hub_name, e)
            raise

    def shutdown(self, *args: Any, clear_temp: bool = False, **kwargs: Any) -> None:
        """Shutdown the ADS connection and optionally clear notifications.

        This method shuts down the current ADS connection and cleans up registered notifications.
        If clear_temp is False, current notifications are saved for later reinitialization.

        """
        hub_name = self.connection_params.get(CONF_ADS_HUB)
        _LOGGER.info("[%s] Shutting down ADS connection", hub_name)

        with self._lock:
            if not clear_temp:
                # Save notifications for reinitialization.
                self._temp_notification_items = list(self._notification_items.values())
                _LOGGER.debug(
                    "[%s] Saving %d notification items for reinitialization",
                    hub_name,
                    len(self._temp_notification_items),
                )
            else:
                self._temp_notification_items.clear()
                _LOGGER.debug("[%s] Temporary notification items cleared", hub_name)

            # Delete notifications from the device.
            failed_deletions = 0
            deletions = 0
            for notification_item in self._notification_items.values():
                _LOGGER.debug(
                    "[%s] Deleting device notification hnotify=%d, huser=%d",
                    hub_name,
                    notification_item.hnotify,
                    notification_item.huser,
                )
                try:
                    self._client.del_device_notification(
                        notification_item.hnotify, notification_item.huser
                    )
                    deletions += 1
                except pyads.ADSError:
                    failed_deletions += 1

            if failed_deletions:
                _LOGGER.warning(
                    "[%s] %d notifications could not be deleted. Continuing with shutdown",
                    hub_name,
                    failed_deletions,
                )
            else:
                _LOGGER.info(
                    "[%s] Deleted %d notifications successfully", hub_name, deletions
                )

            self._notification_items.clear()

            try:
                self._client.close()
                _LOGGER.info("[%s] ADS connection successfully closed", hub_name)
            except pyads.ADSError as err:
                _LOGGER.error("[%s] Error closing ADS connection: %s", hub_name, err)

    def read_state(self) -> Any | None:
        """Read the state from the device.

        Returns:
            The state from the ADS device, or None if an error occurs.

        """
        with self._lock:
            try:
                return self._client.read_state()
            except pyads.ADSError as err:
                hub_name = self.connection_params.get(CONF_ADS_HUB)
                _LOGGER.error("[%s] Error reading ADS state: %s", hub_name, err)
                return None

    def write_by_name(self, name: str, value: Any, plc_datatype: Any) -> Any | None:
        """Write a value to the device by variable name.

        Args:
            name: The variable name.
            value: The value to write.
            plc_datatype: The PLC data type.

        Returns:
            The result of the write operation, or None on error.

        """
        with self._lock:
            try:
                return self._client.write_by_name(name, value, plc_datatype)
            except pyads.ADSError as err:
                hub_name = self.connection_params.get(CONF_ADS_HUB)
                _LOGGER.error("[%s] Error writing %s: %s", hub_name, name, err)
                return None

    def read_by_name(self, name: str, plc_datatype: Any) -> Any | None:
        """Read a value from the device by variable name.

        Args:
            name: The variable name.
            plc_datatype: The PLC data type.

        Returns:
            The value read from the device, or None on error.

        """
        with self._lock:
            try:
                return self._client.read_by_name(name, plc_datatype)
            except pyads.ADSError as err:
                hub_name = self.connection_params.get(CONF_ADS_HUB)
                _LOGGER.error("[%s] Error reading %s: %s", hub_name, name, err)
                return None

    def read_list_by_name(self, data_names: list[str]) -> dict[str, Any] | None:
        """Read multiple values from the device using a list of variable names.

        Args:
            data_names: List of variable names to read.

        Returns:
            A dictionary mapping variable names to their values, or None on error.

        """
        with self._lock:
            try:
                return self._client.read_list_by_name(data_names)
            except pyads.ADSError as err:
                hub_name = self.connection_params.get(CONF_ADS_HUB)
                _LOGGER.error("[%s] Error reading multiple values: %s", hub_name, err)
                return None

    def get_all_symbols(self) -> list[Any] | None:
        """Retrieve all available symbols from the device.

        Returns:
            A list of symbols from the device, or None on error.

        """
        with self._lock:
            try:
                return self._client.get_all_symbols()
            except pyads.ADSError as err:
                hub_name = self.connection_params.get(CONF_ADS_HUB)
                _LOGGER.error("[%s] Error retrieving symbols: %s", hub_name, err)
                return None

    def add_device_notification(
        self, name: str, plc_datatype: Any, callback: Callable[[str, Any], None]
    ) -> None:
        """Add a notification for a given variable on the ADS device.

        Args:
            name: The variable name.
            plc_datatype: The PLC data type.
            callback: Function to call when a notification is received.

        """
        hub_name = self.connection_params.get(CONF_ADS_HUB)
        attr = pyads.NotificationAttrib(ctypes.sizeof(plc_datatype))
        with self._lock:
            try:
                hnotify, huser = self._client.add_device_notification(
                    name, attr, self._device_notification_callback
                )
            except pyads.ADSError as err:
                _LOGGER.error("[%s] Error subscribing to %s: %s", hub_name, name, err)
            else:
                hnotify = int(hnotify)
                self._notification_items[hnotify] = NotificationItem(
                    hnotify, huser, name, plc_datatype, callback
                )
                _LOGGER.debug(
                    "[%s] Added device notification hnotify=%d, huser=%d for variable %s",
                    hub_name,
                    hnotify,
                    huser,
                    name,
                )

    def _device_notification_callback(self, notification: Any, name: str) -> None:
        """Handle device notifications.

        Processes incoming notification data and calls the registered callback.

        """
        hub_name = self.connection_params.get(CONF_ADS_HUB)
        contents = notification.contents
        hnotify = int(contents.hNotification)
        _LOGGER.debug("[%s] Received notification %d", hub_name, hnotify)

        data_size = contents.cbSampleSize
        data_address = (
            ctypes.addressof(contents)
            + pyads.structs.SAdsNotificationHeader.data.offset
        )
        data = (ctypes.c_ubyte * data_size).from_address(data_address)

        with self._lock:
            notification_item = self._notification_items.get(hnotify)

        if not notification_item:
            _LOGGER.error(
                "[%s] Unknown device notification handle: %d", hub_name, hnotify
            )
            return

        plc_datatype = notification_item.plc_datatype
        unpack_formats: dict[Any, str] = {
            pyads.PLCTYPE_BYTE: "<b",
            pyads.PLCTYPE_INT: "<h",
            pyads.PLCTYPE_UINT: "<H",
            pyads.PLCTYPE_SINT: "<b",
            pyads.PLCTYPE_USINT: "<B",
            pyads.PLCTYPE_DINT: "<i",
            pyads.PLCTYPE_UDINT: "<I",
            pyads.PLCTYPE_WORD: "<H",
            pyads.PLCTYPE_DWORD: "<I",
            pyads.PLCTYPE_LREAL: "<d",
            pyads.PLCTYPE_REAL: "<f",
            pyads.PLCTYPE_TOD: "<i",
            pyads.PLCTYPE_DATE: "<i",
            pyads.PLCTYPE_DT: "<i",
            pyads.PLCTYPE_TIME: "<i",
        }
        value: Any
        if plc_datatype == pyads.PLCTYPE_BOOL:
            value = bool(struct.unpack("<?", bytearray(data))[0])
        elif plc_datatype == pyads.PLCTYPE_STRING:
            value = (
                bytearray(data).split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
            )
        elif plc_datatype in unpack_formats:
            value = struct.unpack(unpack_formats[plc_datatype], bytearray(data))[0]
        else:
            value = bytearray(data)
            _LOGGER.warning("[%s] No callback available for this datatype", hub_name)

        notification_item.callback(notification_item.name, value)

    def reinitialize_notifications(self) -> None:
        """Reinitialize notifications and devices after reconnecting.

        This method re-subscribes notifications saved in temporary storage and
        reinitializes registered devices.

        """
        hub_name = self.connection_params.get(CONF_ADS_HUB)
        notifications = 0
        for item in self._temp_notification_items:
            self.add_device_notification(item.name, item.plc_datatype, item.callback)
            notifications += 1
        self._temp_notification_items.clear()
        for device in self._devices:
            try:
                device.initialize_device()
            except Exception as e:  # noqa: BLE001
                _LOGGER.error("[%s] Error initializing device: %s", hub_name, e)
        _LOGGER.info("[%s] Reinitialized %d notifications", hub_name, notifications)

    def read_all_symbols(
        self, template: dict[str, dict[str, Any]] | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        """Read all symbols from the ADS device, filter and categorize them based on a template.

        Args:
            template: A dictionary where keys are entity types (e.g., "light") and values are dictionaries
                    containing the structure name (under CONF_ADS_NAME) and additional fields.

        Returns:
            A dictionary mapping each entity type to a list of filtered symbol dictionaries.

        """

        hub_name = self.connection_params.get(CONF_ADS_HUB)
        template = template or {}

        # Mapping: structure name -> entity type
        struct_to_entity_type: dict[str, str] = {
            type_config[CONF_ADS_NAME]: entity_type
            for entity_type, type_config in template.items()
            if CONF_ADS_NAME in type_config and type_config[CONF_ADS_NAME] is not None
        }

        categorized_symbols: dict[str, list[dict[str, Any]]] = {
            entity_type: [] for entity_type in template
        }

        try:
            symbols = self.get_all_symbols()
            if symbols is None:
                return {}
            _LOGGER.debug(
                "[%s] Retrieved %d symbols from the ADS device", hub_name, len(symbols)
            )
            for symbol in symbols:
                found_struct_name = self._extract_base_type(symbol.symbol_type)
                entity_type = struct_to_entity_type.get(found_struct_name)
                if entity_type:
                    filtered = self._process_symbol(
                        symbol.name, symbol.symbol_type, found_struct_name
                    )
                    categorized_symbols[entity_type].extend(filtered)
        except Exception as e:  # noqa: BLE001
            _LOGGER.error(
                "[%s] Unexpected error while reading symbols: %s", hub_name, e
            )
            return {}
        else:
            self._read_name_and_devicetype_as_list(categorized_symbols, template)
            total_symbols = sum(len(v) for v in categorized_symbols.values())
            platform_symbols = {k: len(v) for k, v in categorized_symbols.items()}
            _LOGGER.info(
                "[%s] Symbols discovered: Total: %d, Details: %s",
                hub_name,
                total_symbols,
                platform_symbols,
            )
            return categorized_symbols

    def _extract_base_type(self, symbol_type: str) -> str:
        """Extract the base type from a symbol type by removing all ARRAY definitions.

        Returns:
            The base type as a string.

        """
        while "ARRAY" in symbol_type:
            match = ArrayRegex.ARRAY_REGEX.search(symbol_type)
            if match:
                symbol_type = match.group(1)
            else:
                break
        return symbol_type

    def _cartesian_product(self, ranges: list[range]) -> Iterable[tuple[int, ...]]:
        """Generate the Cartesian product of a list of ranges.

        Returns:
            An iterable of tuples representing the Cartesian product.

        """
        return product(*ranges)

    def _process_symbol(
        self, symbol_name: str, symbol_type: str, base_structure: str
    ) -> list[dict[str, Any]]:
        """Process a symbol and generate all its instances based on its type.

        Handles nested multi-dimensional arrays dynamically.

        Returns:
            A list of dictionaries containing the symbol path.

        """
        filtered_symbols: list[dict[str, Any]] = []
        if "ARRAY" in symbol_type:
            is_compact, ranges = self._detect_array_type(symbol_type)
            for indices in self._cartesian_product(ranges):
                if is_compact:
                    index_str = f"[{','.join(map(str, indices))}]"
                else:
                    index_str = "".join(f"[{i}]" for i in indices)
                new_symbol_path = f"{symbol_name}{index_str}"
                remaining_type = self._extract_remaining_type(symbol_type)
                if "ARRAY" in remaining_type:
                    filtered_symbols.extend(
                        self._process_symbol(
                            new_symbol_path, remaining_type, base_structure
                        )
                    )
                else:
                    filtered_symbols.append({AdsDiscoveryKeys.ADSPATH: new_symbol_path})
        else:
            filtered_symbols.append({AdsDiscoveryKeys.ADSPATH: symbol_name})
        return filtered_symbols

    def _detect_array_type(self, symbol_type: str) -> tuple[bool, list[range]]:
        """Detect whether the array is compact or nested and extract all ranges.

        Returns:
            A tuple containing a boolean indicating if the array is compact and a list of range objects.

        """

        def parse_dim(dim_str: str) -> range:
            low, high = map(int, dim_str.strip().split(".."))
            return range(min(low, high), max(low, high) + 1)

        compact_match = ArrayRegex.COMPACT_ARRAY_REGEX.match(symbol_type)
        dimensions: list[range] = []
        if compact_match:
            is_compact = True
            dim_ranges = compact_match.group(1)
            dimensions = [parse_dim(dim) for dim in dim_ranges.split(",")]
        else:
            is_compact = False
            # Process nested arrays
            while "ARRAY" in symbol_type:
                nested_match = ArrayRegex.NESTED_ARRAY_REGEX.match(symbol_type)
                if nested_match:
                    dim, symbol_type = nested_match.groups()
                    dimensions.append(parse_dim(dim))
                else:
                    break
        return is_compact, dimensions

    def _extract_remaining_type(self, symbol_type: str) -> str:
        """Extract the remaining type from a symbol type by removing the outermost ARRAY definition.

        Returns:
            The remaining type as a string.

        """
        match = ArrayRegex.ARRAY_REGEX.match(symbol_type)
        return match.group(1) if match else symbol_type

    def _read_name_and_devicetype_as_list(
        self,
        categorized_symbols: dict[str, list[dict[str, Any]]],
        template: dict[str, dict[str, Any]],
    ) -> None:
        """Read and populate metadata for all categorized symbols using a batch ADS read.

        Args:
            categorized_symbols: A mapping from entity types to lists of symbol dictionaries.
            template: The template defining which metadata fields to read.

        """
        hub_name = self.connection_params.get(CONF_ADS_HUB)
        data_names: list[str] = []
        variable_to_symbol_mapping: dict[str, dict[str, str]] = {}

        for entity_type, symbols in categorized_symbols.items():
            template_entity = template.get(entity_type, {})
            ads_fields = template_entity.get(CONF_ADS_FIELDS, {})
            adsvar_name = ads_fields.get(AdsDiscoveryKeys.VAR_NAME)
            adsvar_devicetype = ads_fields.get(AdsDiscoveryKeys.VAR_DEVICE_TYPE)

            if not adsvar_name or not adsvar_devicetype:
                _LOGGER.warning(
                    "[%s] No metadata fields specified for entity type '%s'",
                    hub_name,
                    entity_type,
                )
                continue

            for symbol in symbols:
                path = symbol[AdsDiscoveryKeys.ADSPATH]
                if adsvar_name:
                    name_variable = f"{path}.{adsvar_name}"
                    data_names.append(name_variable)
                    variable_to_symbol_mapping.setdefault(path, {})[
                        AdsDiscoveryKeys.NAME
                    ] = name_variable
                if adsvar_devicetype:
                    devicetype_variable = f"{path}.{adsvar_devicetype}"
                    data_names.append(devicetype_variable)
                    variable_to_symbol_mapping.setdefault(path, {})[
                        AdsDiscoveryKeys.DEVICE_TYPE
                    ] = devicetype_variable

        try:
            results = self.read_list_by_name(data_names)
            if results is None:
                _LOGGER.error("[%s] Failed to read metadata variables", hub_name)
                return
            # Create a flat mapping of symbols to avoid duplicate loops
            all_symbols: dict[str, dict[str, Any]] = {
                symbol[AdsDiscoveryKeys.ADSPATH]: symbol
                for symbols in categorized_symbols.values()
                for symbol in symbols
            }
            for path, keys in variable_to_symbol_mapping.items():
                symbol = all_symbols.get(path, {})
                if symbol is None:
                    continue
                symbol[AdsDiscoveryKeys.NAME] = results.get(
                    keys.get(AdsDiscoveryKeys.NAME, "")
                )
                symbol[AdsDiscoveryKeys.DEVICE_TYPE] = results.get(
                    keys.get(AdsDiscoveryKeys.DEVICE_TYPE, "")
                )
                _LOGGER.debug("[%s] Symbol discovered: %s", hub_name, symbol)

        except pyads.ADSError as err:
            _LOGGER.error("[%s] ADS error while reading metadata: %s", hub_name, err)
        except Exception as e:  # noqa: BLE001
            _LOGGER.error(
                "[%s] Unexpected error while reading metadata for categories: %s",
                hub_name,
                e,
            )
