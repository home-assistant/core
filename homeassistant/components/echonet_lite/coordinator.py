"""Data coordinator for the HEMS integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
import time

from pyhems import (
    CONTROLLER_INSTANCE,
    EOJ,
    EPC_MANUFACTURER_CODE,
    EPC_PRODUCT_CODE,
    EPC_SERIAL_NUMBER,
    ESV_INF_REQ,
    ESV_SET_RES,
    ESV_SET_SNA,
    Frame,
    Property,
    decode_ascii_property,
    parse_property_map,
)
from pyhems.runtime import HemsClient, HemsFrameEvent, HemsInstanceListEvent

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    EPC_GET_PROPERTY_MAP,
    EPC_INF_PROPERTY_MAP,
    EPC_SET_PROPERTY_MAP,
    STABLE_CLASS_CODES,
)
from .types import EchonetLiteConfigEntry, EchonetLiteNodeState

_LOGGER = logging.getLogger(__name__)


class EchonetLiteCoordinator(DataUpdateCoordinator[dict[str, EchonetLiteNodeState]]):
    """Coordinator that tracks state for detected SEOJ nodes."""

    config_entry: EchonetLiteConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config_entry: EchonetLiteConfigEntry,
        client: HemsClient,
        monitored_epcs: Mapping[int, frozenset[int]],
        enable_experimental: bool,
    ) -> None:
        """Initialize the coordinator for a specific config entry."""

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=None,
            config_entry=config_entry,
        )
        self.data: dict[str, EchonetLiteNodeState] = {}
        # Track newly added device keys for entity platforms to process
        # Cleared after listener notification completes
        self.new_device_keys: set[str] = set()
        # Track pending setup requests to prevent duplicate property map requests
        # Key is device_key (node_id-eoj)
        self._pending_setups: set[str] = set()
        # NOTE: HEMS integration assumes ECHONET Lite devices include an
        # identification number (EPC 0x83). This integration treats missing
        # identification numbers as a device that does not comply with the
        # specification and ignores instance list placeholders and migrations.
        self.last_frame_received_at: float | None = None
        self.client = client
        # Mapping of class_code -> monitored EPCs (what HA platforms want to read)
        # Includes both MRA-based and vendor-specific EPCs
        self._monitored_epcs = monitored_epcs
        # Node profile info cache: node_id -> (product_code, serial_number)
        # Used to populate HemsNodeState with initial values from node profile
        self._node_profile_info: dict[str, tuple[str | None, str | None]] = {}
        self._enable_experimental = enable_experimental

    async def async_process_frame_event(self, event: HemsFrameEvent) -> None:
        """Store a decoded frame and notify listeners.

        Nodes are created only when property maps (0x9F) are received.
        Frames for unknown nodes without property maps are ignored.
        """
        frame = event.frame
        eoj = event.eoj
        node_id = event.node_id

        # Early exit for non-response frames (we only process responses and failure responses)
        if not frame.is_response_frame():
            return

        timestamp = event.received_at

        device_key = f"{node_id}-{eoj:06x}"
        existing = self.data.get(device_key)

        # We no longer create nodes here; initial creation happens via
        # _async_setup_device (async_get result). If we get a frame
        # for an unknown device, skip to avoid duplicate/partial setup.
        if existing is None:
            _LOGGER.debug(
                "Ignoring frame for unknown node %s %r (setup handled elsewhere)",
                device_key,
                eoj,
            )
            return

        self.last_frame_received_at = timestamp

        _LOGGER.debug(
            "Received frame for %s (ESV=0x%02X): %r",
            device_key,
            frame.esv,
            frame.properties,
        )

        # Set responses (0x71) and Set failure responses (0x51) do not carry
        # the current property values. They are acknowledgements and may
        # include empty EDT (PDC=0) for accepted properties.
        # Do not let these frames overwrite stored state.
        if frame.esv in (ESV_SET_RES, ESV_SET_SNA):
            return

        # Update properties
        updated = False
        for prop in frame.properties:
            # Only update if value changed or it's a new property
            current = existing.properties.get(prop.epc)
            if current is None or current != prop.edt:
                existing.properties[prop.epc] = prop.edt
                updated = True

        if updated:
            self.async_update_listeners()

    async def async_process_instance_list_event(
        self, event: HemsInstanceListEvent
    ) -> None:
        """Process an instance list event from pyhems.

        This only requests property maps for newly discovered EOJs.
        Nodes are NOT created here - they are created when property maps
        are received in async_process_frame_event.
        """
        node_id = event.node_id

        # Extract product_code and serial_number from node profile properties
        product_code = decode_ascii_property(
            event.properties.get(EPC_PRODUCT_CODE, b"")
        )
        serial_number = decode_ascii_property(
            event.properties.get(EPC_SERIAL_NUMBER, b"")
        )

        # Cache node profile info for later use
        # These values may be overwritten by device class responses
        if product_code or serial_number:
            self._node_profile_info[node_id] = (product_code, serial_number)

        # Find new EOJs that we haven't seen before
        for eoj in event.instances:
            device_key = f"{node_id}-{eoj:06x}"
            if device_key not in self.data and device_key not in self._pending_setups:
                # Filter out experimental device classes unless enabled
                if (
                    not self._enable_experimental
                    and eoj.class_code not in STABLE_CLASS_CODES
                ):
                    _LOGGER.debug(
                        "Skipping experimental device class 0x%04X from node %s "
                        "(enable_experimental is disabled)",
                        eoj.class_code,
                        node_id,
                    )
                    continue
                self._pending_setups.add(device_key)
                _LOGGER.debug("Discovered new %r from node %s", eoj, node_id)
                await self._async_setup_device(event.node_id, eoj)

    async def _async_setup_device(self, node_id: str, eoj: EOJ) -> None:
        """Set up a device by requesting its properties and creating an EchonetLiteNodeState.

        Uses async_get with automatic retry for partial responses
        (ESV=0x52). This combines multiple requests into a single ESV=0x62 Get:
        - 0x8A: Manufacturer code (device identification)
        - 0x8D: Serial number (device identification)
        - 0x9D: Status change announcement (INF) property map
        - 0x9E: Set property map
        - 0x9F: Get property map
        - Required EPCs for the device class (initial values)

        The async_get method handles ESV=0x52 partial responses by
        automatically retrying failed EPCs.

        Args:
            node_id: Device node ID (hex string from EPC 0x83).
            eoj: ECHONET object instance.
        """
        device_key = f"{node_id}-{eoj:06x}"
        try:
            # Base EPCs: device identification + property maps
            base_epcs = [
                EPC_INF_PROPERTY_MAP,
                EPC_SET_PROPERTY_MAP,
                EPC_GET_PROPERTY_MAP,
                EPC_MANUFACTURER_CODE,
                EPC_PRODUCT_CODE,
                EPC_SERIAL_NUMBER,
            ]

            # Get monitored EPCs for this device class (initial values)
            initial_epcs = self._monitored_epcs.get(eoj.class_code, frozenset())
            monitored_epcs = initial_epcs - set(base_epcs)

            # Combine base EPCs and monitored EPCs (preserving order)
            all_epcs = base_epcs + list(monitored_epcs)

            _LOGGER.debug(
                "Requesting property maps, device ID, "
                "for node %s %r: base=[%s], monitored=[%s]",
                node_id,
                eoj,
                " ".join(f"{epc:02X}" for epc in base_epcs),
                " ".join(f"{epc:02X}" for epc in sorted(monitored_epcs)),
            )

            # Use async_get with automatic retry for partial responses
            response_props = await self.client.async_get(node_id, eoj, all_epcs)
            properties: dict[int, bytes] = {
                prop.epc: prop.edt for prop in response_props if prop.edt
            }

            timestamp = time.monotonic()
            get_epcs: frozenset[int] = frozenset()
            set_epcs: frozenset[int] = frozenset()
            inf_epcs: frozenset[int] = frozenset()
            manufacturer_code: int | None = None
            serial_number: str | None = None

            # Parse special properties by dict lookup
            if EPC_GET_PROPERTY_MAP in properties:
                get_epcs = parse_property_map(properties[EPC_GET_PROPERTY_MAP])
            if EPC_SET_PROPERTY_MAP in properties:
                set_epcs = parse_property_map(properties[EPC_SET_PROPERTY_MAP])
            if EPC_INF_PROPERTY_MAP in properties:
                inf_epcs = parse_property_map(properties[EPC_INF_PROPERTY_MAP])
            if EPC_MANUFACTURER_CODE in properties:
                edt = properties[EPC_MANUFACTURER_CODE]
                if len(edt) >= 3:
                    manufacturer_code = int.from_bytes(edt[:3], "big")
            serial_number = decode_ascii_property(
                properties.get(EPC_SERIAL_NUMBER, b"")
            )

            # manufacturer_code is required - skip devices without it
            if manufacturer_code is None:
                _LOGGER.warning(
                    "Device %s has no manufacturer code (EPC 0x8A), skipping",
                    device_key,
                )
                self._pending_setups.discard(device_key)
                return

            # Parse product code from device class response
            product_code = decode_ascii_property(properties.get(EPC_PRODUCT_CODE, b""))

            # Fall back to node profile info if device class response is empty
            np_info = self._node_profile_info.get(node_id)
            if np_info:
                np_product_code, np_serial_number = np_info
                if not product_code and np_product_code:
                    product_code = np_product_code
                if not serial_number and np_serial_number:
                    serial_number = np_serial_number

            # Compute EPCs to poll: definition EPCs that are GET-able but not INF-announced
            poll_epcs = frozenset((initial_epcs & get_epcs) - inf_epcs)

            node = EchonetLiteNodeState(
                eoj=eoj,
                properties=properties,
                last_seen=timestamp,
                node_id=node_id,
                get_epcs=get_epcs,
                set_epcs=set_epcs,
                inf_epcs=inf_epcs,
                poll_epcs=poll_epcs,
                manufacturer_code=manufacturer_code,
                product_code=product_code,
                serial_number=serial_number,
            )

            self.last_frame_received_at = timestamp

            new_snapshot = dict(self.data)
            new_snapshot[device_key] = node

            self.new_device_keys.add(device_key)
            self.async_set_updated_data(new_snapshot)
            self.new_device_keys.clear()

            # Send a one-time 0x63 notification request right after creation
            await self._async_send_initial_notification(device_key, node)

            self._pending_setups.discard(device_key)
            _LOGGER.info(
                "Created new node %s with %d properties, get=[%s] set=[%s] inf=[%s]",
                device_key,
                len(properties),
                bytes(sorted(get_epcs)).hex(),
                bytes(sorted(set_epcs)).hex(),
                bytes(sorted(inf_epcs)).hex(),
            )

        except Exception:
            # If setup fails, remove from pending so it can be retried
            self._pending_setups.discard(device_key)
            _LOGGER.exception("Failed to request property maps for %r", eoj)

    async def _async_send_initial_notification(
        self, device_key: str, node: EchonetLiteNodeState
    ) -> None:
        """Send a one-time 0x63 notification request for required EPCs."""

        epcs = set(self._monitored_epcs.get(node.eoj.class_code, frozenset()))
        epcs &= node.inf_epcs

        if not epcs:
            return

        frame = Frame(
            seoj=CONTROLLER_INSTANCE,
            deoj=node.eoj,
            esv=ESV_INF_REQ,
            properties=[Property(epc=epc, edt=b"") for epc in epcs],
        )

        _LOGGER.debug(
            "Sending initial 0x63 notification request to node %s for EPCs: [%s]",
            device_key,
            " ".join(f"{epc:02X}" for epc in sorted(epcs)),
        )

        try:
            await self.client.async_send(node.node_id, frame)
        except OSError as err:
            _LOGGER.debug(
                "Failed to send initial notifications for node %s: %s",
                device_key,
                err,
            )
