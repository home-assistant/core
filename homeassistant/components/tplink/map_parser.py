"""Map parser for TP-Link smart home devices."""

from base64 import b64decode
from typing import Literal, TypedDict

import lz4.block
import numpy as np

type VacuumCoordinate = tuple[int, int, int]


class GetRoomsResponse(TypedDict):
    """Get rooms response."""

    rooms: dict[int, str]
    map_id: int


class GetCurrentRoomResponse(TypedDict):
    """Get current room response."""

    current_room: int


type MapDataAreaItem = MapDataRoomItem | MapDataVirtualWallItem


class MapData(TypedDict):
    """Map data."""

    map_id: int
    name: str
    vac_coor: VacuumCoordinate
    real_vac_coor: VacuumCoordinate | None
    map_locked: bool
    resolution: int
    resolution_unit: str
    width: int
    height: int
    origin_coor: VacuumCoordinate
    real_origin_coor: VacuumCoordinate
    pix_len: int
    map_hash: str
    pix_lz4len: str
    map_data: str
    area_list: list[MapDataAreaItem]


class MapDataRoomItem(TypedDict):
    """Map data room item."""

    type: Literal["room"]
    id: int
    name: str
    color: int
    suction: int
    cistern: int
    clean_number: int
    floor_texture: int
    carpet_strategy: int


class MapDataVirtualWallItem(TypedDict):
    """Map data virtual wall item."""

    type: Literal["virtual_wall"]
    id: int
    vertexs: list[list[int]]  # List of [x, y] pairs


room_map_cache: dict[
    str, np.ndarray[tuple[int, int], np.dtype[np.unsignedinteger]]
] = {}


class TpLinkMapParser:
    """Parse the map data."""

    _map_data: MapData

    def __init__(self, map_data: MapData) -> None:
        """Initialize the map parser."""
        self._map_data = map_data

    def get_rooms(self) -> dict[int, str]:
        """Parse the map data."""
        rooms: dict[int, str] = {}
        for room in self._map_data["area_list"]:
            if room["type"] == "room":
                rooms[room["id"]] = b64decode(room["name"]).decode("utf-8")

        return rooms

    def get_current_room(self) -> GetCurrentRoomResponse | None:
        """Get the current room."""
        # we're assuming the vacuum coordinates are 2d
        if self._map_data["real_vac_coor"] is None:
            return None

        rooms = self.get_rooms()
        room_map = self._get_room_map(rooms)

        if room_map is None:
            return None

        pixel_x = int(
            (self._map_data["real_vac_coor"][0] - self._map_data["real_origin_coor"][0])
            / self._map_data["resolution"]
        )
        pixel_y = int(
            (self._map_data["real_vac_coor"][1] - self._map_data["real_origin_coor"][1])
            / self._map_data["resolution"]
        )

        # Ensure within bounds
        pixel_x = max(0, min(pixel_x, self._map_data["width"] - 1))
        pixel_y = max(0, min(pixel_y, self._map_data["height"] - 1))

        room_id: int | None = room_map[pixel_y, pixel_x]

        if room_id not in rooms:
            return None

        return {"current_room": int(room_id)}

    def _get_room_map(self, rooms: dict[int, str]) -> np.ndarray | None:
        cached_array = room_map_cache.get(self._map_data["map_hash"])
        if cached_array is not None:
            return cached_array

        map_array = self._decode_map_data()
        if map_array is None:
            return None

        # Convert to room IDs
        # Values 1-100 are typically used for room IDs
        room_map = np.zeros(
            (self._map_data["height"], self._map_data["width"]), dtype=np.uint8
        )

        for i in rooms:
            # Find pixels with this room ID
            room_map[map_array == i] = i

        room_map_cache[self._map_data["map_hash"]] = room_map

        return room_map

    def _decode_map_data(
        self,
    ) -> np.ndarray | None:
        """Decode the map data to get the pixel-by-pixel representation."""
        if "map_data" not in self._map_data or not self._map_data["map_data"]:
            return None

        # Decode the base64 map data
        compressed_data = b64decode(self._map_data["map_data"])
        decompressed_data = lz4.block.decompress(
            compressed_data, self._map_data["pix_len"]
        )

        # This gives us a 2D array where each pixel value indicates:
        # - Values 1-7 (in your case): Room IDs (corresponds to area_list items with type "room")
        # - 255: Cleanable space that's not in a specific room
        # - Other values: Barriers, walls, or non-cleanable areas
        return np.frombuffer(decompressed_data, dtype=np.uint8).reshape(
            self._map_data["height"], self._map_data["width"]
        )
