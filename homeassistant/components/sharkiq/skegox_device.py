# Device model for Shark vacuums via the Skegox API.
# Implements the same interface as the legacy SharkIqVacuum class so that
# the existing vacuum.py entity code works unchanged.

from __future__ import annotations

import base64
import json
import logging
import struct
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .skegox_api import SkegoxApi

from .const import ERROR_MESSAGES

_LOGGER = logging.getLogger(__name__)

# Coordinate transformation from protobuf local grid to JSON centimeters.
# Derived from comparing protobuf float32 values against known MARD JSON coordinates.
# x_json = -(50/3) * x_proto + 134.5
# y_json = (50/3) * y_proto + 203.5
_COORD_SCALE = 50.0 / 3.0
_COORD_X_OFFSET = 134.5
_COORD_Y_OFFSET = 203.5

# Skegox property names (GET_ prefix for read, SET_ prefix for write)
# These map to the same logical properties as the Ayla API but with
# consistent GET_/SET_ prefixes in the shadow model.
PROP_OPERATING_MODE = "GET_Operating_Mode"
PROP_CHARGING_STATUS = "GET_Charging_Status"
PROP_BATTERY_CAPACITY = "GET_Battery_Capacity"
PROP_ERROR_CODE = "GET_Error_Code"
PROP_POWER_MODE = "GET_Power_Mode"
PROP_RSSI = "GET_RSSI"
PROP_ROBOT_ROOM_LIST = "GET_Robot_Room_List"
PROP_LOW_LIGHT_MISSION = "GET_LowLightMission"
PROP_RECHARGE_RESUME = "GET_Recharge_Resume"
PROP_RECHARGING_TO_RESUME = "GET_Recharging_To_Resume"
PROP_ROBOT_FIRMWARE_VERSION = "GET_Robot_Firmware_Version"
PROP_DEVICE_MODEL_NUMBER = "GET_Device_Model_Number"

# Settable property names (without GET_ prefix, as the API expects)
SET_OPERATING_MODE = "Operating_Mode"
SET_POWER_MODE = "Power_Mode"
SET_FIND_DEVICE = "Find_Device"
SET_AREAS_TO_CLEAN = "Areas_To_Clean"
SET_AREAS_TO_CLEAN_V3 = "AreasToClean_V3"

# Operating mode values (match the Ayla API IntEnum values)
OP_MODE_STOP = 0
OP_MODE_PAUSE = 1
OP_MODE_START = 2
OP_MODE_RETURN = 3

# Power mode values (match the Ayla API IntEnum values)
POWER_ECO = 1
POWER_NORMAL = 0
POWER_MAX = 2

# Translation from Ayla power mode values to Skegox power mode values.
# The old Ayla API uses ECO=1, NORMAL=0, MAX=2 while Skegox uses
# ECO=0, NORMAL=1, MAX=2.
AYLA_TO_SKEGOX_POWER = { POWER_ECO: 0, POWER_NORMAL: 1, POWER_MAX: 2, }

SKEGOX_TO_AYLA_POWER = {v: k for k, v in AYLA_TO_SKEGOX_POWER.items()}

# Represents a Shark vacuum via the Skegox API.
# Implements the same public interface as SharkIqVacuum so that the
# existing vacuum.py entity code works without modification.
class SkegoxDevice:
    
    # Extract device SND (serial number) from registry data.
    # The SND is derived from `Battery_Serial_Num`, taking the portion
    # after the last `-` separator (e.g., `ABC-123-XYZ456` → `XYZ456`).
    @staticmethod
    def extract_snd(registry: dict[str, Any]) -> str:
        bsn = registry.get("Battery_Serial_Num", "")
        return bsn.split("-")[-1] if "-" in bsn else bsn

    # Merge source properties into target with optional prefix.
    # Each value is wrapped as `{"value": value}` to match the unified
    # property access pattern used across both backends.
    @staticmethod
    def _merge_properties(target: dict[str, Any], source: dict[str, Any], prefix: str = "") -> None:
        for key, value in source.items():
            prop_key = f"{prefix}{key}"
            if isinstance(value, dict):
                target[prop_key] = value
            else:
                target[prop_key] = {"value": value}

    # Create a SkegoxDevice from a Skegox API response.
    # `device_data` structure:
    #   `metadata`: device name and display info
    #   `registry`: hardware serial numbers, model, firmware
    #   `telemetry`: real-time sensor readings
    #   `connectivityStatus`: online/offline state
    #   `shadow`: IoT shadow with `reported` and `desired` properties
    def __init__(self, api: SkegoxApi, device_data: dict[str, Any]) -> None:
        self._api = api
        self._raw = device_data

        metadata = device_data.get("metadata", {})
        registry = device_data.get("registry", {})
        telemetry = device_data.get("telemetry", {})
        connectivity = device_data.get("connectivityStatus", {})
        shadow = device_data.get("shadow", {})
        reported = shadow.get("properties", {}).get("reported", {})

        # Extract SND: prefer stored _snd from API, fall back to Battery_Serial_Num
        self._snd = device_data.get("_snd", "")
        if not self._snd:
            self._snd = SkegoxDevice.extract_snd(registry)
        self._dsn = self._snd

        self._name = metadata.get("deviceName", "Shark Robot")
        self._oem_model = registry.get("Device_Serial_Num", "")
        self._model_number = registry.get("Device_Model_Number", "")
        self._connection_status = ("Online" if connectivity.get("connected") else "Offline")

        # Build properties dict from telemetry + shadow reported
        self.properties_full: dict[str, Any] = {}
        self._merge_properties(self.properties_full, telemetry, prefix="GET_")
        self._merge_properties(self.properties_full, reported, prefix="GET_")

        # Firmware from registry
        fw = registry.get("FW_VERSION", "")
        if fw:
            self.properties_full[PROP_ROBOT_FIRMWARE_VERSION] = {"value": fw}

        # Device model number from registry
        model = registry.get("Device_Model_Number", "")
        if model:
            self.properties_full[PROP_DEVICE_MODEL_NUMBER] = {"value": model}

        # Parse room list
        self._floor_id: str = ""
        self._rooms: list[str] = []
        self._room_name_map: dict[str, str] = {}
        self._mard_raw: dict[str, Any] | None = None
        self._room_polygons: dict[str, list[tuple[float, float]]] = {}
        self._no_go_zones: list[dict[str, Any]] = []
        self._parse_room_list(reported)

        # Floor plan image and edges (from floorRPfile1)
        self._floor_plan_image: Any = None
        self._floor_plan_edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
        self._floor_plan_doors: list[tuple[tuple[float, float], tuple[float, float]]] = []
        self._floor_plan_scale: float = 0.06
        self._floor_plan_origin: tuple[float, float] = (0.0, 0.0)
        self._floor_plan_dims: tuple[int, int] = (0, 0)

        # Detect AreasToClean_V3 capability
        self._has_areas_v3 = "AreasToClean_V3" in reported

    @property
    def serial_number(self) -> str:
        return self._dsn

    @property
    def name(self) -> str:
        return self._name

    @property
    def oem_model_number(self) -> str:
        return self._oem_model

    @property
    def vac_model_number(self) -> str | None:
        model = self.get_property_value(PROP_DEVICE_MODEL_NUMBER)
        return str(model) if model else None

    @property
    def error_code(self) -> int | None:
        return self.get_property_value(PROP_ERROR_CODE)

    @property
    def error_text(self) -> str | None:
        err = self.error_code
        if err:
            return ERROR_MESSAGES.get(err, f"Unknown error ({err})")
        return None

    # Get the value of a property.
    # Accepts both string names and enum values (for compatibility
    # with the legacy Properties enum). Tries the raw name first,
    # then the GET_-prefixed name used by the Skegox shadow model.
    def get_property_value(self, property_name: str | Any) -> Any:
        name = property_name.value if hasattr(property_name, "value") else property_name
        # Try raw name first (matches Ayla API property names)
        prop = self.properties_full.get(name)
        # Fall back to GET_-prefixed name (Skegox shadow model)
        if prop is None and not name.startswith("GET_"):
            prop = self.properties_full.get(f"GET_{name}")
        if prop is None:
            return None
        if isinstance(prop, dict):
            value = prop.get("value")
        else:
            value = prop
        # Translate power mode values from Skegox to Ayla
        if name in (PROP_POWER_MODE, "Power_Mode", "GET_Power_Mode") and value in SKEGOX_TO_AYLA_POWER:
            return SKEGOX_TO_AYLA_POWER[value]
        return value

    # Set a property value via the Skegox API.
    # Strips the ``GET_`` prefix if present — the API expects the base
    # property name for writes (e.g., ``GET_Power_Mode`` → ``Power_Mode``).
    # Also translates Ayla power mode values to Skegox equivalents.
    async def async_set_property_value(self, property_name: str | Any, value: Any) -> None:
        name = property_name.value if hasattr(property_name, "value") else property_name
        # Strip GET_ prefix if present, the API expects the base name
        if name.startswith("GET_"):
            name = name[4:]
        if hasattr(value, "value"):
            value = value.value
        # Translate power mode values from Ayla to Skegox
        if name == "Power_Mode" and value in AYLA_TO_SKEGOX_POWER:
            value = AYLA_TO_SKEGOX_POWER[value]
        await self._api.set_desired_property(self._snd, name, value)

    # Set the operating mode.
    async def async_set_operating_mode(self, mode: Any) -> None:
        mode_val = mode.value if hasattr(mode, "value") else mode
        await self._api.set_desired_property(self._snd, SET_OPERATING_MODE, mode_val)

    # Make the device emit a chirp.
    async def async_find_device(self) -> None:
        await self._api.set_desired_property(self._snd, SET_FIND_DEVICE, 1)

    # Clean specific rooms.
    async def async_clean_rooms(self, rooms: list[str]) -> None:
        await self._api.clean_rooms(snd=self._snd, rooms=rooms, floor_id=self._floor_id, use_v3=self._has_areas_v3,)

    # Parse room list from Robot_Room_List or AreasToClean_V3 property.
    #   Format A (legacy): "FloorID:Room1:Room2:..."
    #   Format B (v3 JSON): {"floor_id": "...", "areas_to_clean": {"UserRoom": ["Kitchen", "Living Room"]}}
    def _parse_room_list(self, reported: dict[str, Any]) -> None:
        # Try Robot_Room_List first (legacy colon-separated format)
        room_list_raw = reported.get("Robot_Room_List", {})
        room_list_val = (
            room_list_raw.get("value", room_list_raw)
            if isinstance(room_list_raw, dict)
            else room_list_raw
        )
        if room_list_val and isinstance(room_list_val, str) and ":" in room_list_val:
            parts = room_list_val.split(":")
            self._floor_id = parts[0]
            self._rooms = parts[1:]
            return

        # Try AreasToClean variants in order of preference
        for prop_name in ("AreasToClean_V3", "AreasToClean_V2", "Areas_To_Clean"):
            floor_id, rooms = self._parse_areas_json(prop_name, reported)
            if rooms:
                self._floor_id = floor_id
                self._rooms = rooms
                return

    # Try to parse areas data from a property. Returns (floor_id, rooms) or (None, None).
    def _parse_areas_json(self, prop_name: str, reported: dict[str, Any]) -> tuple[str | None, list[str] | None]:
        prop_data = reported.get(prop_name, {})
        prop_val = prop_data.get("value", prop_data) if isinstance(prop_data, dict) else prop_data
        if not prop_val:
            return None, None

        try:
            parsed = json.loads(prop_val) if isinstance(prop_val, str) else prop_val
            if not isinstance(parsed, dict):
                return None, None

            floor_id = parsed.get("floor_id", "")
            areas = parsed.get("areas_to_clean", {})

            # V3 dict-of-lists format: {"UserRoom": ["Kitchen", "Living Room"]}
            if isinstance(areas, dict):
                all_rooms = []
                for room_list in areas.values():
                    if isinstance(room_list, list):
                        all_rooms.extend(room_list)
                if all_rooms:
                    return floor_id, all_rooms
            # V2/legacy flat list format: ["Room1", "Room2"]
            elif isinstance(areas, list):
                rooms = [item.split(":", 1)[-1] if ":" in item else item for item in areas]
                return floor_id, rooms
        except (ValueError, TypeError):
            pass

        return None, None

    # Parse floorRPfile1 protobuf data into an image and edge/door segments.
    def parse_floor_plan(self, data: bytes) -> None:
        self._floor_plan_raw = data
        try:
            self._parse_floor_plan_protobuf(data)
        except Exception:
            _LOGGER.debug("Floor plan parse failed for %s", self._name, exc_info=True)

    # Parse floorRPfile1 protobuf structure.
    #   Key fields:
    #   - Field 5/21: image container (scale, origin, dimensions, pixel data)
    #   - Field 28: repeated edge/door line entries
    def _parse_floor_plan_protobuf(self, data: bytes) -> None:
        cp = 0

        field_data: dict[int, bytes] = {}
        field_varints: dict[int, int] = {}
        field_floats: dict[int, float] = {}
        field_28_entries: list[bytes] = []

        while cp < len(data):
            tag, cp = _read_varint(data, cp)
            fn = tag >> 3
            wt = tag & 7

            if wt == 2:
                length, cp = _read_varint(data, cp)
                if fn == 28:
                    field_28_entries.append(data[cp:cp + length])
                else:
                    field_data[fn] = data[cp:cp + length]
                cp += length
            elif wt == 0:
                val, cp = _read_varint(data, cp)
                field_varints[fn] = val
            elif wt == 5:
                val = struct.unpack('<f', data[cp:cp + 4])[0]
                cp += 4
                field_floats[fn] = val
            else:
                break

        # Parse image from field 21 (or field 5)
        img_raw = field_data.get(21) or field_data.get(5)
        if img_raw:
            self._parse_floor_image(img_raw)

        # Parse edges/doors from repeated field 28 entries
        for entry in field_28_entries:
            self._parse_floor_edge_entry(entry)

    # Parse image container from field 5/21.
    #   Sub-fields:
    #   - Field 1: scale (float, meters per pixel)
    #   - Field 2: origin (x, y floats)
    #   - Field 3: width (varint)
    #   - Field 4: height (varint)
    #   - Field 6: pixel data (palette-indexed bytes)
    #   - Field 10: palette colors (parsed separately)
    def _parse_floor_image(self, data: bytes) -> None:
        from PIL import Image

        cp = 0
        scale = 0.06
        origin_x = 0.0
        origin_y = 0.0
        width = 0
        height = 0
        pixel_data: bytes = b""

        while cp < len(data):
            tag, cp = _read_varint(data, cp)
            fn = tag >> 3
            wt = tag & 7

            if wt == 5:
                val = struct.unpack('<f', data[cp:cp + 4])[0]
                cp += 4
                if fn == 1:
                    scale = val
            elif wt == 2:
                length, cp = _read_varint(data, cp)
                fd = data[cp:cp + length]
                cp += length
                if fn == 2:
                    if len(fd) >= 10:
                        origin_x = struct.unpack('<f', fd[1:5])[0]
                        origin_y = struct.unpack('<f', fd[6:10])[0]
                elif fn == 6:
                    pixel_data = fd
            elif wt == 0:
                val, cp = _read_varint(data, cp)
                if fn == 3:
                    width = val
                elif fn == 4:
                    height = val
            else:
                break

        if not pixel_data or width == 0 or height == 0:
            return

        self._floor_plan_scale = scale
        self._floor_plan_origin = (origin_x, origin_y)
        self._floor_plan_dims = (width, height)

        # Parse palette from field 10
        palette = self._parse_palette()

        # Convert palette-indexed pixels to RGBA image
        img = Image.new("RGBA", (width, height))
        pixels = img.load()
        for py in range(height):
            for px in range(width):
                idx = py * width + px
                if idx < len(pixel_data):
                    color_idx = pixel_data[idx]
                    if palette and color_idx < len(palette):
                        r, g, b = palette[color_idx]
                        pixels[px, py] = (r, g, b, 255)
                    else:
                        gray = min(255, color_idx * 2)
                        pixels[px, py] = (gray, gray, gray, 255)
                else:
                    pixels[px, py] = (0, 0, 0, 0)
        self._floor_plan_image = img
        _LOGGER.info("Floor plan image loaded for %s: %dx%d, scale=%.2fm/px, palette=%d colors", self._name, width, height, scale, len(palette),)

    # Parse palette from field 10.
    # Returns a list of (R, G, B) tuples indexed by palette index.
    #   Field 10 sub-fields:
    #   - Field 2: palette count (varint, default 256)
    #   - Field 3: palette data (byte array of RGB entries)
    def _parse_palette(self) -> list[tuple[int, int, int]]:
        field_10_raw: bytes | None = None

        # Re-read the raw data to find field 10
        # We need to access the original floor plan data, but we don't have it here.
        # Instead, we'll parse it from a stored copy.
        if self._floor_plan_raw is None:
            return []

        data = self._floor_plan_raw
        cp = 0
        while cp < len(data):
            tag, cp = _read_varint(data, cp)
            fn = tag >> 3
            wt = tag & 7
            if wt == 2:
                length, cp = _read_varint(data, cp)
                if fn == 10:
                    field_10_raw = data[cp:cp + length]
                    break
                cp += length
            elif wt == 0:
                _, cp = _read_varint(data, cp)
            elif wt == 5:
                cp += 4
            else:
                break

        if not field_10_raw:
            return []

        # Parse palette entries from field 10
        # Structure: field 1 (float scale), field 2 (varint count), field 3 (palette data)
        cp = 0
        palette_count = 256  # default
        palette_data: bytes = b""

        while cp < len(field_10_raw):
            tag, cp = _read_varint(field_10_raw, cp)
            fn = tag >> 3
            wt = tag & 7
            if wt == 0:
                val, cp = _read_varint(field_10_raw, cp)
                if fn == 2:
                    palette_count = val
            elif wt == 2:
                length, cp = _read_varint(field_10_raw, cp)
                if fn == 3:
                    palette_data = field_10_raw[cp:cp + length]
                cp += length
            elif wt == 5:
                cp += 4
            else:
                break

        # Parse palette data as repeated entries
        # Each entry appears to be a small struct with RGB values
        palette: list[tuple[int, int, int]] = [(0, 0, 0)] * palette_count

        cp = 0
        idx = 0
        while cp < len(palette_data) and idx < palette_count:
            tag, cp = _read_varint(palette_data, cp)
            fn = tag >> 3
            wt = tag & 7
            if wt == 2:
                length, cp = _read_varint(palette_data, cp)
                fd = palette_data[cp:cp + length]
                cp += length
                if length == 3:
                    palette[idx] = (fd[0], fd[1], fd[2])
                    idx += 1
                elif length >= 3:
                    # Try to extract RGB from longer entries
                    # Pattern: 14 00 0c 00 fe ff 14 00 07 00 fd ff ...
                    # Every 5 bytes: <varint> <R> <G> <B>
                    pp = 0
                    while pp < len(fd) and idx < palette_count:
                        if pp + 3 < len(fd):
                            r = fd[pp]
                            g = fd[pp + 1]
                            b = fd[pp + 2]
                            palette[idx] = (r, g, b)
                            idx += 1
                            pp += 3
                        else:
                            break
            elif wt == 0:
                _, cp = _read_varint(palette_data, cp)
            elif wt == 5:
                cp += 4
            else:
                break

        return palette

    # Parse a single edge/door entry from field 28.
    #   Sub-fields:
    #   - Field 2: edge type string ("edge" or "door")
    #   - Field 4: points container with repeated (x, y) float pairs
    def _parse_floor_edge_entry(self, entry: bytes) -> None:
        ep = 0
        edge_type = ""
        points: list[tuple[float, float]] = []

        while ep < len(entry):
            tag2, ep = _read_varint(entry, ep)
            fn2 = tag2 >> 3
            wt2 = tag2 & 7

            if wt2 == 2:
                length2, ep = _read_varint(entry, ep)
                fd = entry[ep:ep + length2]
                ep += length2

                if fn2 == 2:
                    edge_type = fd.decode("utf-8", errors="replace")
                elif fn2 == 4:
                    # Points container: repeated entries of format
                    # 0a <len=12> 0d <x_float> 15 <y_float> 18 <flag>
                    pp = 0
                    while pp < len(fd):
                        ptag, pp = _read_varint(fd, pp)
                        pfn = ptag >> 3
                        pwt = ptag & 7
                        if pwt == 2:
                            plen, pp = _read_varint(fd, pp)
                            pdata = fd[pp:pp + plen]
                            pp += plen
                            if len(pdata) >= 10:
                                x = struct.unpack('<f', pdata[1:5])[0]
                                y = struct.unpack('<f', pdata[6:10])[0]
                                points.append((x * 100, y * 100))
                        elif pwt == 0:
                            _, pp = _read_varint(fd, pp)
                        else:
                            break
            elif wt2 == 0:
                _, ep = _read_varint(entry, ep)
            else:
                break

        if len(points) >= 2:
            if edge_type == "door":
                self._floor_plan_doors.append((points[0], points[1]))
            elif edge_type == "edge":
                for i in range(len(points) - 1):
                    self._floor_plan_edges.append((points[i], points[i + 1]))

    # Parse MARD (Mobile_App_Room_Definition) data and populate rooms.
    # Accepts either JSON format (legacy) or base64-encoded protobuf
    # (newer Skegox devices, stored in the 'zones' property file).
    def load_mard(self, mard_body: bytes) -> None:
        try:
            parsed = json.loads(mard_body.decode("utf-8"))
            self._load_mard_json(parsed)
            return
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

        # Try base64-encoded protobuf
        try:
            decoded = base64.b64decode(mard_body)
            self._load_mard_protobuf(decoded)
            return
        except Exception:
            _LOGGER.debug("MARD for %s: not valid JSON or base64 protobuf", self._name)

    # Parse MARD JSON format.
    # `area_meta_data` prefixes identify the area type:
    # "UserRoom:" — a cleanable room with a name
    # "UserNoGo:" — a no-go zone (UUID after the colon)
    def _load_mard_json(self, parsed: dict[str, Any]) -> None:
        if not self._mard_raw:
            _LOGGER.debug("MARD full structure for %s: %s", self._name, json.dumps(parsed, indent=2)[:2000],)

        self._mard_raw = parsed

        name_map: dict[str, str] = {}
        rooms: list[str] = []
        room_polygons: dict[str, list[tuple[float, float]]] = {}
        no_go_zones: list[dict[str, Any]] = []

        for area in parsed.get("areas", []):
            meta = area.get("area_meta_data", "")
            points_raw = area.get("points", [])
            points = [(p["x"], p["y"]) for p in points_raw if "x" in p and "y" in p]

            if meta.startswith("UserRoom:"):
                robot_name = area.get("robot_room_name", "") or ""
                user_name = area.get("user_room_name", "") or ""
                if not robot_name:
                    continue
                display_name = user_name or robot_name
                name_map[robot_name] = display_name
                rooms.append(display_name)
                if points:
                    room_polygons[display_name] = points

            elif meta.startswith("UserNoGo:"):
                uuid_val = meta.split(":", 1)[1] if ":" in meta else ""
                area_state = area.get("area_state", "blocking")
                if points:
                    no_go_zones.append({"uuid": uuid_val, "points": points, "area_state": area_state, })

        mard_floor_id = parsed.get("floor_id")
        if isinstance(mard_floor_id, str) and mard_floor_id:
            self._floor_id = mard_floor_id

        if rooms:
            self._rooms = rooms
            self._room_name_map = name_map
            self._room_polygons = room_polygons
            _LOGGER.info("MARD rooms for %s: %s", self._name, rooms)
        else:
            _LOGGER.debug("MARD for %s: no rooms found", self._name)

        if no_go_zones:
            self._no_go_zones = no_go_zones
            _LOGGER.info("MARD no-go zones for %s: %d", self._name, len(no_go_zones))

    # Parse base64-decoded protobuf zones data.
    #   Structure:
    #   - Field 6: main container
    #       - Field 3: floor_id (string)
    #       - Field 15: room entries (repeated)
    #           - Field 2: room name (string)
    #           - Field 4: points container
    #               - Repeated field 1 entries, each with x (field 1, 32-bit) and y (field 2, 32-bit)
    #           - Field 16: no-go zone
    #               - Field 2: uuid (string)
    #               - Field 4: points container (same format as rooms)
    #               - Field 16: zone type string (e.g., "No-Go")
    def _load_mard_protobuf(self, data: bytes) -> None:
        pos = 0
        tag, pos = _read_varint(data, pos)
        if (tag >> 3) != 6:
            _LOGGER.debug("Protobuf MARD: expected field 6, got %d", tag >> 3)
            return

        length, pos = _read_varint(data, pos)
        container = data[pos:pos + length]

        name_map: dict[str, str] = {}
        rooms: list[str] = []
        room_polygons: dict[str, list[tuple[float, float]]] = {}
        no_go_zones: list[dict[str, Any]] = []

        cp = 0
        while cp < len(container):
            tag, cp = _read_varint(container, cp)
            fn = tag >> 3
            wt = tag & 7

            if wt != 2:
                if wt == 0:
                    _, cp = _read_varint(container, cp)
                continue

            field_len, cp = _read_varint(container, cp)
            field_data = container[cp:cp + field_len]
            cp += field_len

            if fn == 3:
                self._floor_id = field_data.decode("utf-8")

            elif fn == 15:
                room_name, points = _parse_room_protobuf(field_data)
                if room_name and points:
                    name_map[room_name] = room_name
                    rooms.append(room_name)
                    room_polygons[room_name] = points

            elif fn == 16:
                uuid_val, zone_points, zone_type = _parse_nogo_protobuf(field_data)
                if zone_points:
                    no_go_zones.append({"uuid": uuid_val, "points": zone_points, "area_state": "blocking",})

        if rooms:
            self._rooms = rooms
            self._room_name_map = name_map
            self._room_polygons = room_polygons
            self._mard_raw = {"floor_id": self._floor_id, "areas": []}
            _LOGGER.info("MARD rooms for %s: %s", self._name, rooms)
        else:
            _LOGGER.debug("MARD protobuf for %s: no rooms found", self._name)

        if no_go_zones:
            self._no_go_zones = no_go_zones
            _LOGGER.info("MARD no-go zones for %s: %d", self._name, len(no_go_zones))

    @property
    def floor_id(self) -> str:
        return self._floor_id

    @property
    def rooms(self) -> list[str]:
        return self._rooms

    @property
    def room_name_map(self) -> dict[str, str]:
        return self._room_name_map

    # Return the raw MARD data if loaded.
    @property
    def mard_data(self) -> dict[str, Any] | None:
        return self._mard_raw

    @property
    def has_areas_v3(self) -> bool:
        return self._has_areas_v3

    @property
    def room_polygons(self) -> dict[str, list[tuple[float, float]]]:
        return self._room_polygons

    @property
    def no_go_zones(self) -> list[dict[str, Any]]:
        return self._no_go_zones

    @property
    def floor_plan_image(self) -> Any:
        return self._floor_plan_image

    @property
    def floor_plan_edges(self) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        return self._floor_plan_edges

    @property
    def floor_plan_doors(self) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        return self._floor_plan_doors

    @property
    def floor_plan_scale(self) -> float:
        return self._floor_plan_scale

    @property
    def floor_plan_origin(self) -> tuple[float, float]:
        return self._floor_plan_origin

    @property
    def connection_status(self) -> str:
        return self._connection_status

    # Update device state from a fresh Skegox API response.
    # Note: This uses last-known-value semantics — properties that disappear
    # from the API response retain their previous value in properties_full.
    # This is intentional to avoid flickering state during transient API gaps.
    def update_from_response(self, device_data: dict[str, Any]) -> None:
        telemetry = device_data.get("telemetry", {})
        shadow = device_data.get("shadow", {})
        reported = shadow.get("properties", {}).get("reported", {})
        connectivity = device_data.get("connectivityStatus", {})

        self._connection_status = ("Online" if connectivity.get("connected") else "Offline")

        # Update telemetry properties
        for key, value in telemetry.items():
            self.properties_full[f"GET_{key}"] = {"value": value}

        # Update shadow reported properties
        for key, val_obj in reported.items():
            if isinstance(val_obj, dict):
                self.properties_full[f"GET_{key}"] = val_obj
            else:
                self.properties_full[f"GET_{key}"] = {"value": val_obj}

# Read a protobuf varint, returning (value, new_position).
# See https://protobuf.dev/programming-guides/encoding/#varints
def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        result |= (byte & 0x7F) << shift
        pos += 1
        if (byte & 0x80) == 0:
            break
        shift += 7
    return result, pos

# Transform protobuf local grid coordinates to JSON centimeter coordinates.
# Scale and offset constants were derived empirically by comparing
#  protobuf float32 values against known MARD JSON coordinates.
def _transform_coord(x: float, y: float) -> tuple[float, float]:
    x_json = -_COORD_SCALE * x + _COORD_X_OFFSET
    y_json = _COORD_SCALE * y + _COORD_Y_OFFSET
    return x_json, y_json

# Parse a room entry from protobuf. Returns (name, list of (x, y) points).
def _parse_room_protobuf(data: bytes) -> tuple[str, list[tuple[float, float]]]:
    rp = 0
    room_name = ""
    points: list[tuple[float, float]] = []

    while rp < len(data):
        tag, rp = _read_varint(data, rp)
        fn = tag >> 3
        wt = tag & 7

        if wt != 2:
            continue

        field_len, rp = _read_varint(data, rp)
        field_data = data[rp:rp + field_len]
        rp += field_len

        if fn == 2:
            room_name = field_data.decode("utf-8")

        elif fn == 4:
            pp = 0
            while pp < len(field_data):
                ptag, pp = _read_varint(field_data, pp)
                pfn = ptag >> 3
                pwt = ptag & 7

                if pwt != 2:
                    continue

                plen, pp = _read_varint(field_data, pp)
                pdata = field_data[pp:pp + plen]
                pp += plen

                if len(pdata) >= 10:
                    x_raw = struct.unpack("<f", pdata[1:5])[0]
                    y_raw = struct.unpack("<f", pdata[6:10])[0]
                    points.append(_transform_coord(x_raw, y_raw))

    return room_name, points

# Parse a no-go zone entry from protobuf. Returns (uuid, points, type).
def _parse_nogo_protobuf(data: bytes) -> tuple[str, list[tuple[float, float]], str]:
    np = 0
    uuid_val = ""
    zone_type = ""
    points: list[tuple[float, float]] = []

    while np < len(data):
        tag, np = _read_varint(data, np)
        fn = tag >> 3
        wt = tag & 7

        if wt == 0:
            _, np = _read_varint(data, np)
            continue

        if wt != 2:
            continue

        field_len, np = _read_varint(data, np)
        field_data = data[np:np + field_len]
        np += field_len

        if fn in (2, 3):
            uuid_val = field_data.decode("utf-8")

        elif fn == 16:
            zone_type = field_data.decode("utf-8")

        elif fn == 4:
            pp = 0
            while pp < len(field_data):
                ptag, pp = _read_varint(field_data, pp)
                pfn = ptag >> 3
                pwt = ptag & 7

                if pwt != 2:
                    continue

                plen, pp = _read_varint(field_data, pp)
                pdata = field_data[pp:pp + plen]
                pp += plen

                if len(pdata) >= 10:
                    x_raw = struct.unpack("<f", pdata[1:5])[0]
                    y_raw = struct.unpack("<f", pdata[6:10])[0]
                    points.append(_transform_coord(x_raw, y_raw))

    return uuid_val, points, zone_type