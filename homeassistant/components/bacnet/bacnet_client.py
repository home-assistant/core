"""BACnet client wrapper for Home Assistant."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
import ipaddress
import socket
from typing import TYPE_CHECKING, Any

try:
    import netifaces

    HAS_NETIFACES = True
except ImportError:
    HAS_NETIFACES = False

from .const import (
    COV_LIFETIME,
    DISCOVERY_TIMEOUT,
    MULTISTATE_OBJECT_TYPES,
    TIMEOUT_COV_GET_VALUE,
    TIMEOUT_OBJECT_LIST_READ,
    TIMEOUT_PROPERTY_READ,
    TIMEOUT_PROPERTY_READ_SHORT,
    WRITE_PRIORITY,
)

if TYPE_CHECKING:
    from bacpypes3.app import Application
    from bacpypes3.basetypes import PropertyValue
    from bacpypes3.primitivedata import ObjectIdentifier


class BACnetWriteError(Exception):
    """Raised when a BACnet write operation fails."""


def _format_interface_label(iface: str, addr_info: dict[str, str]) -> str | None:
    """Format a network interface label from address info, or None if loopback."""
    ip = str(addr_info.get("addr", ""))
    if not ip or ip.startswith("127."):
        return None
    netmask = addr_info.get("netmask", "")
    if netmask:
        try:
            network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
        except ValueError:
            return f"{iface} ({ip})"
        else:
            return f"{iface} {network.network_address}-{network.broadcast_address}"
    return f"{iface} ({ip})"


def _get_local_interfaces_sync() -> dict[str, str]:
    """Get available local network interfaces (sync).

    Returns:
        Ordered dictionary with interface names mapped to descriptions with IP.
        Special keys: "0.0.0.0" (all interfaces), "manual" (manual entry).
    """
    temp_interfaces = {}

    # Use netifaces for comprehensive interface enumeration if available
    if HAS_NETIFACES:
        for iface in netifaces.interfaces():  # pylint: disable=c-extension-no-member
            addrs = netifaces.ifaddresses(iface)  # pylint: disable=c-extension-no-member
            if netifaces.AF_INET in addrs:  # pylint: disable=c-extension-no-member
                for addr_info in addrs[netifaces.AF_INET]:  # pylint: disable=c-extension-no-member
                    label = _format_interface_label(iface, addr_info)
                    if label:
                        temp_interfaces[iface] = label
    else:
        try:
            # Get all IP addresses associated with this host
            hostname = socket.gethostname()
            # Get all address info for the hostname
            addrs = socket.getaddrinfo(hostname, None, socket.AF_INET)

            for addr in addrs:
                ip = str(addr[4][0])
                # Skip loopback
                if not ip.startswith("127."):
                    # Without netifaces, use IP as the "interface name"
                    temp_interfaces[ip] = f"{ip} ({hostname})"
        except Exception:  # noqa: BLE001
            pass

        # Also try to get IP by connecting to a public address (doesn't actually connect)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            # Use Google DNS to determine which interface would be used for internet
            s.connect(("8.8.8.8", 80))
            default_ip = s.getsockname()[0]
            s.close()
            if default_ip and not default_ip.startswith("127."):
                if default_ip not in temp_interfaces:
                    temp_interfaces[default_ip] = f"{default_ip} (default route)"
        except Exception:  # noqa: BLE001
            pass

    # Build ordered dict with sorted interface names first, then special options last
    interfaces = {}

    # Sort interfaces by name
    for iface in sorted(temp_interfaces.keys()):
        interfaces[iface] = temp_interfaces[iface]

    # Add manual entry option
    interfaces["manual"] = "Enter IP address manually..."

    return interfaces


async def get_local_interfaces() -> dict[str, str]:
    """Get available local network interfaces.

    Returns:
        Dictionary mapping interface names to descriptions with IP.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _get_local_interfaces_sync)


def _resolve_interface_to_ip_sync(interface: str) -> str:
    """Resolve interface name to IP address (sync).

    Args:
        interface: Interface name (e.g., "eth0"), IP address, or special value "0.0.0.0".

    Returns:
        IP address to bind to.
    """
    # Special cases
    if interface in {"0.0.0.0", "manual"}:
        return interface

    # If it's already an IP address, return as-is
    try:
        socket.inet_aton(interface)
    except OSError:
        # Not an IP address, try to resolve interface name to IP
        if HAS_NETIFACES:
            try:
                addrs = netifaces.ifaddresses(interface)  # pylint: disable=c-extension-no-member
                if netifaces.AF_INET in addrs:  # pylint: disable=c-extension-no-member
                    return addrs[netifaces.AF_INET][0]["addr"]  # pylint: disable=c-extension-no-member
            except ValueError, KeyError, IndexError:
                pass
    else:
        return interface

    # Fallback: assume it's already an IP
    return interface


async def resolve_interface_to_ip(interface: str) -> str:
    """Resolve interface name to IP address.

    Args:
        interface: Interface name (e.g., "eth0"), IP address, or special value "0.0.0.0".

    Returns:
        IP address to bind to.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _resolve_interface_to_ip_sync, interface)


@dataclass
class BACnetDeviceInfo:
    """Represent a discovered BACnet device."""

    device_id: int
    address: str
    name: str = ""
    vendor_name: str = ""
    model_name: str = ""
    firmware_revision: str = ""
    description: str = ""
    mac_address: str = ""
    hardware_version: str = ""


@dataclass
class BACnetObjectInfo:
    """Represent a BACnet object on a device."""

    object_type: str
    object_instance: int
    object_name: str = ""
    present_value: Any = None
    units: str = ""
    description: str = ""
    status_flags: list[bool] = field(default_factory=list)
    state_text: list[str] = field(default_factory=list)


class BACnetClient:
    """Manage BACnet communication using BACpypes3."""

    def __init__(self) -> None:
        """Initialize the BACnet client."""
        self._app: Application | None = None
        self._cov_tasks: dict[str, asyncio.Task[None]] = {}
        self._cov_callbacks: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        """Return whether the client is connected."""
        return self._app is not None

    async def connect(self, local_address: str, device_instance: int) -> None:
        """Initialize the BACnet application stack.

        Args:
            local_address: Local BACnet address in format "ip_address/netmask"
                          or "ip_address" (e.g., "192.168.21.223/24" or "0.0.0.0")
            device_instance: Unique BACnet device object instance (0–4,194,302).
        """
        if self._app is not None:
            return

        # Add netmask if not present (BACpypes3 requires CIDR notation)
        if "/" not in local_address:
            local_address = f"{local_address}/24"

        # Create argparse.Namespace with all required fields for Application.from_args()
        args = argparse.Namespace(
            name="Home Assistant",
            instance=device_instance,
            vendoridentifier=999,
            address=local_address,
            network=0,
            foreign=None,
            ttl=30,
            bbmd=None,
        )

        # Import at runtime to avoid import-time issues
        from bacpypes3.app import Application  # noqa: PLC0415

        self._app = Application.from_args(args)

    async def disconnect(self) -> None:
        """Shut down the BACnet application stack."""
        # Cancel all COV subscription tasks
        for task in self._cov_tasks.values():
            task.cancel()
        self._cov_tasks.clear()
        self._cov_callbacks.clear()

        if self._app is not None:
            # Cancel all pending BACnet transaction retry timers before
            # closing the transport, otherwise bacpypes3 SSMs keep firing
            # retries on a dead socket.
            if hasattr(self._app, "asap"):
                for ssm in list(self._app.asap.clientTransactions):
                    if hasattr(ssm, "_timer_handle") and ssm._timer_handle:  # noqa: SLF001
                        ssm._timer_handle.cancel()  # noqa: SLF001
                        ssm._timer_handle = None  # noqa: SLF001
                for ssm in list(self._app.asap.serverTransactions):
                    if hasattr(ssm, "_timer_handle") and ssm._timer_handle:  # noqa: SLF001
                        ssm._timer_handle.cancel()  # noqa: SLF001
                        ssm._timer_handle = None  # noqa: SLF001

            self._app.close()
            self._app = None

    async def discover_device_at_address(
        self,
        address: str,
        timeout: int = DISCOVERY_TIMEOUT,
    ) -> BACnetDeviceInfo | None:
        """Discover a BACnet device at a specific IP address using directed WhoIs.

        This sends a unicast WhoIs to the given address rather than a broadcast,
        useful for devices that are not discoverable via broadcast.

        Returns the first device found at that address, or None.
        """
        from bacpypes3.pdu import Address  # noqa: PLC0415

        if self._app is None:
            raise RuntimeError("BACnet client is not connected")

        i_am_responses = await self._app.who_is(
            address=Address(address),
            timeout=timeout,
        )

        if not i_am_responses:
            return None

        response = i_am_responses[0]
        device_id = response.iAmDeviceIdentifier[1]
        device_address = str(response.pduSource)

        device_info = BACnetDeviceInfo(
            device_id=device_id,
            address=device_address,
            name=f"Device {device_id}",
        )

        # Read object name for better display
        obj_ref = f"device,{device_id}"
        try:
            async with asyncio.timeout(TIMEOUT_PROPERTY_READ_SHORT):
                device_info.name = await self._read_property_safe(
                    device_address,
                    obj_ref,
                    "objectName",
                    default=f"Device {device_id}",
                )
        except TimeoutError:
            pass

        return device_info

    async def discover_devices(
        self,
        timeout: int = DISCOVERY_TIMEOUT,
        low_limit: int | None = None,
        high_limit: int | None = None,
    ) -> list[BACnetDeviceInfo]:
        """Discover BACnet devices on the network using WhoIs."""
        if self._app is None:
            raise RuntimeError("BACnet client is not connected")

        i_am_responses = await self._app.who_is(
            low_limit=low_limit,
            high_limit=high_limit,
            timeout=timeout,
        )

        devices: list[BACnetDeviceInfo] = []
        for response in i_am_responses:
            device_id = response.iAmDeviceIdentifier[1]
            address = str(response.pduSource)

            # Create device info with ID and address from IAm response
            device_info = BACnetDeviceInfo(
                device_id=device_id,
                address=address,
                name=f"Device {device_id}",  # Default name
            )

            # Read basic device properties for better display in config flow
            # Use individual timeouts to handle slow devices gracefully
            obj_ref = f"device,{device_id}"
            try:
                async with asyncio.timeout(TIMEOUT_PROPERTY_READ_SHORT):
                    device_info.name = await self._read_property_safe(
                        address, obj_ref, "objectName", default=f"Device {device_id}"
                    )
            except TimeoutError:
                pass

            try:
                async with asyncio.timeout(TIMEOUT_PROPERTY_READ_SHORT):
                    device_info.vendor_name = await self._read_property_safe(
                        address, obj_ref, "vendorName", default=""
                    )
            except TimeoutError:
                pass

            try:
                async with asyncio.timeout(TIMEOUT_PROPERTY_READ_SHORT):
                    device_info.model_name = await self._read_property_safe(
                        address, obj_ref, "modelName", default=""
                    )
            except TimeoutError:
                pass

            try:
                async with asyncio.timeout(TIMEOUT_PROPERTY_READ_SHORT):
                    device_info.firmware_revision = await self._read_property_safe(
                        address, obj_ref, "firmwareRevision", default=""
                    )
            except TimeoutError:
                pass

            try:
                async with asyncio.timeout(TIMEOUT_PROPERTY_READ_SHORT):
                    device_info.description = await self._read_property_safe(
                        address, obj_ref, "description", default=""
                    )
            except TimeoutError:
                pass

            # Try to read hardware version (application software version is an alternative)
            try:
                async with asyncio.timeout(TIMEOUT_PROPERTY_READ_SHORT):
                    device_info.hardware_version = await self._read_property_safe(
                        address, obj_ref, "applicationSoftwareVersion", default=""
                    )
            except TimeoutError:
                pass

            # Try to read MAC address from network-port object
            # Most BACnet/IP devices have a network-port object at instance 1
            try:
                async with asyncio.timeout(TIMEOUT_PROPERTY_READ_SHORT):
                    mac_value = await self._read_property_safe(
                        address, "network-port,1", "macAddress", default=None
                    )
                    if mac_value:
                        # Convert MAC address to standard format
                        if isinstance(mac_value, (list, tuple)):
                            device_info.mac_address = ":".join(
                                f"{b:02x}" for b in mac_value
                            )
                        elif isinstance(mac_value, str):
                            device_info.mac_address = mac_value
            except TimeoutError:
                pass

            devices.append(device_info)

        return devices

    async def get_device_objects(
        self,
        address: str,
        device_id: int,
        quick: bool = False,
    ) -> list[BACnetObjectInfo]:
        """Read the object list from a BACnet device.

        Args:
            address: Device network address
            device_id: BACnet device ID
            quick: If True, only read object names (fast). If False, read all properties (slow).
        """
        from bacpypes3.apdu import ErrorRejectAbortNack  # noqa: PLC0415
        from bacpypes3.basetypes import EngineeringUnits  # noqa: PLC0415
        from bacpypes3.primitivedata import ObjectIdentifier, Unsigned  # noqa: PLC0415

        if self._app is None:
            raise RuntimeError("BACnet client is not connected")

        # Read the object list with timeout to prevent hanging
        try:
            async with asyncio.timeout(TIMEOUT_OBJECT_LIST_READ):
                object_list = await self._app.read_property(
                    address,
                    f"device,{device_id}",
                    "objectList",
                )
        except ErrorRejectAbortNack:
            object_list = await self._read_object_list_by_index(address, device_id)

        objects: list[BACnetObjectInfo] = []
        if not object_list:
            return objects

        for obj_id in object_list:
            if isinstance(obj_id, ObjectIdentifier):
                obj_type = str(obj_id[0])
                obj_instance = obj_id[1]
            else:
                continue

            # Skip device objects
            if obj_type == "device":
                continue

            obj_info = BACnetObjectInfo(
                object_type=obj_type,
                object_instance=obj_instance,
            )

            # Read object properties
            obj_ref = f"{obj_type},{obj_instance}"
            try:
                # Always read object name (needed for entity creation)
                obj_info.object_name = await self._read_property_safe(
                    address, obj_ref, "objectName", default=""
                )

                # Always read units (needed for proper entity setup)
                units_val = await self._read_property_safe(
                    address, obj_ref, "units", default=None
                )
                if units_val is not None:
                    if isinstance(units_val, EngineeringUnits):
                        # Use .attr to get camelCase attribute name (e.g., "degreesCelsius")
                        obj_info.units = units_val.attr
                    elif isinstance(units_val, (int, Unsigned)):
                        try:
                            # Convert numeric to enum and get attribute name
                            obj_info.units = EngineeringUnits(int(units_val)).attr
                        except ValueError, KeyError:
                            obj_info.units = str(units_val)
                    else:
                        obj_info.units = str(units_val)

                # Read stateText for multi-state objects (enumeration labels)
                if obj_type in MULTISTATE_OBJECT_TYPES:
                    state_text_val = await self._read_property_safe(
                        address, obj_ref, "stateText", default=None
                    )
                    if state_text_val is not None:
                        obj_info.state_text = _parse_state_text(state_text_val)

                # Skip presentValue and description in quick mode (for fast UI response)
                if not quick:
                    raw_value = await self._read_property_safe(
                        address, obj_ref, "presentValue", default=None
                    )
                    obj_info.present_value = _convert_bacnet_value(raw_value)

                    obj_info.description = await self._read_property_safe(
                        address, obj_ref, "description", default=""
                    )
            except Exception:  # noqa: BLE001
                pass

            objects.append(obj_info)

        return objects

    async def read_present_value(
        self,
        address: str,
        object_type: str,
        object_instance: int,
    ) -> Any:
        """Read the present value of a BACnet object."""
        if self._app is None:
            raise RuntimeError("BACnet client is not connected")

        obj_ref = f"{object_type},{object_instance}"
        # Add timeout to prevent hanging HA
        async with asyncio.timeout(TIMEOUT_PROPERTY_READ):
            raw_value = await self._app.read_property(address, obj_ref, "presentValue")
        return _convert_bacnet_value(raw_value)

    async def write_present_value(
        self,
        address: str,
        object_type: str,
        object_instance: int,
        value: object,
        priority: int = WRITE_PRIORITY,
    ) -> None:
        """Write a value to a BACnet object's present value."""
        from bacpypes3.apdu import ErrorRejectAbortNack  # noqa: PLC0415

        if self._app is None:
            raise RuntimeError("BACnet client is not connected")

        obj_ref = f"{object_type},{object_instance}"
        try:
            async with asyncio.timeout(TIMEOUT_PROPERTY_READ):
                response = await self._app.write_property(
                    address, obj_ref, "presentValue", value, priority=priority
                )
        except ErrorRejectAbortNack as err:
            raise BACnetWriteError(str(err)) from err

        if isinstance(response, ErrorRejectAbortNack):
            raise BACnetWriteError(str(response))

    async def subscribe_cov(
        self,
        address: str,
        object_type: str,
        object_instance: int,
        callback: Any,
    ) -> str:
        """Subscribe to COV notifications for a BACnet object."""
        if self._app is None:
            raise RuntimeError("BACnet client is not connected")

        sub_key = f"{address}:{object_type},{object_instance}"
        self._cov_callbacks[sub_key] = callback

        task = asyncio.create_task(
            self._cov_subscription_loop(address, object_type, object_instance, sub_key)
        )
        self._cov_tasks[sub_key] = task

        return sub_key

    async def unsubscribe_cov(self, subscription_key: str) -> None:
        """Unsubscribe from COV notifications."""
        if subscription_key in self._cov_tasks:
            self._cov_tasks[subscription_key].cancel()
            del self._cov_tasks[subscription_key]

        self._cov_callbacks.pop(subscription_key, None)

    async def _cov_subscription_loop(
        self,
        address: str,
        object_type: str,
        object_instance: int,
        sub_key: str,
    ) -> None:
        """Maintain a COV subscription and forward notifications."""
        from bacpypes3.pdu import Address  # noqa: PLC0415
        from bacpypes3.primitivedata import ObjectIdentifier  # noqa: PLC0415

        if self._app is None:
            return

        obj_id = ObjectIdentifier(f"{object_type},{object_instance}")
        addr = Address(address)

        while True:
            try:
                cov_context = self._app.change_of_value(
                    addr,
                    obj_id,
                    issue_confirmed_notifications=False,
                    lifetime=COV_LIFETIME,
                )
                async with cov_context as subscription:
                    while True:
                        # Add timeout to prevent hanging forever waiting for COV
                        async with asyncio.timeout(TIMEOUT_COV_GET_VALUE):
                            property_value: PropertyValue = (
                                await subscription.get_value()
                            )
                        if sub_key in self._cov_callbacks:
                            values = _extract_cov_values(property_value)
                            self._cov_callbacks[sub_key](values)
            except asyncio.CancelledError:
                return
            except Exception:  # noqa: BLE001
                try:
                    await asyncio.sleep(30)
                except asyncio.CancelledError:
                    return

    async def _read_property_safe(
        self,
        address: str,
        obj_ref: str,
        prop: str,
        default: Any = None,
    ) -> Any:
        """Read a property, returning a default on failure."""
        if self._app is None:
            return default
        try:
            # Add timeout to prevent hanging
            async with asyncio.timeout(TIMEOUT_PROPERTY_READ):
                return await self._app.read_property(address, obj_ref, prop)
        except BaseException:  # noqa: BLE001
            # BACpypes3 errors may not inherit from Exception
            return default

    async def _read_object_list_by_index(
        self,
        address: str,
        device_id: int,
    ) -> list[ObjectIdentifier]:
        """Read the object list one element at a time as a fallback."""
        from bacpypes3.primitivedata import ObjectIdentifier  # noqa: PLC0415

        if self._app is None:
            return []

        obj_ref = f"device,{device_id}"
        try:
            # Timeout for reading array count
            async with asyncio.timeout(TIMEOUT_PROPERTY_READ):
                count_result = await self._app.read_property(
                    address, obj_ref, "objectList", array_index=0
                )
            count = int(count_result)
        except Exception:  # noqa: BLE001
            return []

        objects: list[ObjectIdentifier] = []
        for i in range(1, count + 1):
            try:
                # Timeout for each individual object read
                async with asyncio.timeout(TIMEOUT_PROPERTY_READ_SHORT):
                    obj_id = await self._app.read_property(
                        address, obj_ref, "objectList", array_index=i
                    )
                if isinstance(obj_id, ObjectIdentifier):
                    objects.append(obj_id)
            except Exception:  # noqa: BLE001
                continue

            # Yield control every 10 objects to prevent blocking event loop
            if i % 10 == 0:
                await asyncio.sleep(0)

        return objects


def _parse_state_text(raw_value: Any) -> list[str]:
    """Parse a BACnet stateText array into a list of strings.

    BACnet stateText is a 1-indexed array of CharacterString values
    that provide human-readable labels for each multi-state value.
    """
    if raw_value is None:
        return []

    if isinstance(raw_value, (list, tuple)) or hasattr(raw_value, "__iter__"):
        texts = [str(item).strip() for item in raw_value]
    else:
        texts = [str(raw_value).strip()]

    # Filter out empty strings
    return [t for t in texts if t]


def _convert_bacnet_value(raw_value: Any) -> Any:
    """Convert a BACnet value to a Python native type."""
    from bacpypes3.constructeddata import AnyAtomic  # noqa: PLC0415
    from bacpypes3.primitivedata import (  # noqa: PLC0415
        BitString,
        CharacterString,
        Date,
        Double,
        Enumerated,
        Integer,
        Null,
        Real,
        Time,
        Unsigned,
    )

    if raw_value is None or isinstance(raw_value, Null):
        return None
    if isinstance(raw_value, (Real, Double)):
        return float(raw_value)
    if isinstance(raw_value, (Integer, Unsigned)):
        return int(raw_value)
    if isinstance(raw_value, Enumerated):
        return int(raw_value)
    if isinstance(raw_value, CharacterString):
        return str(raw_value)
    if isinstance(raw_value, (bool,)):
        return raw_value
    if isinstance(raw_value, BitString):
        return [bool(b) for b in raw_value]
    if isinstance(raw_value, (Date, Time)):
        return str(raw_value)
    if isinstance(raw_value, AnyAtomic):
        return str(raw_value)
    if isinstance(raw_value, (int, float, str)):
        return raw_value
    return str(raw_value)


def _extract_cov_values(property_value: Any) -> dict[str, Any]:
    """Extract values from a COV notification."""
    values: dict[str, Any] = {}
    if isinstance(property_value, (tuple, list)):
        for item in property_value:
            if hasattr(item, "propertyIdentifier") and hasattr(item, "value"):
                prop_id = str(item.propertyIdentifier)
                values[prop_id] = _convert_bacnet_value(item.value)
    elif hasattr(property_value, "propertyIdentifier") and hasattr(
        property_value, "value"
    ):
        prop_id = str(property_value.propertyIdentifier)
        values[prop_id] = _convert_bacnet_value(property_value.value)
    return values
