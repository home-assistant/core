"""Network helpers for Home Assistant."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable
import heapq
import math
import random
from typing import TYPE_CHECKING, TypeVar, cast

from homeassistant.const import (
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
    SERVICE_CLOSE,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_LOCK,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_OPEN,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_RELOAD,
    SERVICE_REPEAT_SET,
    SERVICE_SAVE_PERSISTENT_STATES,
    SERVICE_SELECT_OPTION,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_SHUFFLE_SET,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    SERVICE_TOGGLE,
    SERVICE_TOGGLE_COVER_TILT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_UNLOCK,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)

if TYPE_CHECKING:
    from .entity import VirtualEntity

_services = [
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
    SERVICE_TOGGLE,
    SERVICE_RELOAD,
    SERVICE_VOLUME_UP,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_STOP,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_TRIGGER,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    SERVICE_OPEN,
    SERVICE_CLOSE,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SAVE_PERSISTENT_STATES,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    SERVICE_TOGGLE_COVER_TILT,
    SERVICE_SELECT_OPTION,
    "async_update_ha_state",
]
_services = _services + ["async_" + service for service in _services]

RT = TypeVar("RT")


class NetworkProxy:
    """Network proxy for entity."""

    def __init__(self, proxied_object):
        """Init proxy."""
        self.__dict__["__proxied"] = proxied_object

    def __setattr__(self, name, value):
        """Set attribute."""
        setattr(self.__dict__["__proxied"], name, value)

    def __repr__(self):
        """Return the representation."""
        return f"<proxy entity={repr(self.__dict__['__proxied'])}>"

    def __getattr__(self, attr):
        """Get attribute with network proxy."""
        obj = getattr(self.__dict__["__proxied"], attr)
        if not callable(obj) or (
            not asyncio.iscoroutinefunction(obj) and obj.__name__ not in _services
        ):
            return obj

        async def wrapped_method(*args, **kwargs):
            is_service = attr in _services
            owd = getattr(self.__dict__["__proxied"], "owd")
            if is_service:
                # create latency
                await asyncio.sleep(owd)
            try:
                if asyncio.iscoroutinefunction(obj):
                    res = await cast(Awaitable[RT], obj(*args, **kwargs))
                else:
                    res = cast(RT, obj(*args, **kwargs))
            finally:
                if is_service:
                    # create latency
                    await asyncio.sleep(owd)
            return res

        return wrapped_method


def _find_k_min_dis(k, locations):
    disheap = []
    dis_map = {}
    for i, _ in enumerate(locations):
        for j in range(i + 1, len(locations)):
            distance = _dis(locations[i], locations[j])
            dis_map[(i, j)] = distance
            if len(disheap) < k:
                heapq.heappush(disheap, -distance)
            elif distance > disheap[0]:
                heapq.heapreplace(disheap, -distance)
    k_min_distances = []
    while disheap:
        k_min_distances.insert(0, -heapq.heappop(disheap))
    return k_min_distances, dis_map


def _find_k_min_dis_per_node(k, locations, dims):
    disheap = []
    dis_map = {}
    for i, _ in enumerate(locations):
        mindis = sum(dims)  # check if enough
        for j, _ in enumerate(locations):
            if i == j:
                continue
            if (j, i) in dis_map:
                distance = dis_map.get((j, i))
            else:
                distance = _dis(locations[i], locations[j])
                dis_map[(i, j)] = distance
            mindis = min(mindis, distance)
        # print("i, mindis:", i, mindis)

        if len(disheap) < k:
            heapq.heappush(disheap, mindis)
        elif distance > disheap[0]:
            heapq.heapreplace(disheap, mindis)


def _dis(v1, v2):
    distance = 0.0
    for i in enumerate(v1):
        distance += (v1[i] - v2[i]) * (v1[i] - v2[i])
    distance = math.sqrt(distance)
    return distance


def _get_threshold(locations, dims):  # the min threshold to make the network connected
    curmax = 0
    dis_map = {}
    for i, _ in enumerate(locations):
        mindis = sum(dims)  # check if enough
        for j, _ in enumerate(locations):
            if i == j:
                continue
            if (j, i) in dis_map:
                distance = dis_map.get((j, i))
            else:
                distance = _dis(locations[i], locations[j])
                dis_map[(i, j)] = distance
            mindis = min(mindis, distance)
        curmax = max(curmax, mindis)
    return curmax, dis_map


def _get_topology(locations, dis_map, threshold):
    topology = {}
    for i, _ in enumerate(locations):
        for j in range(i + 1, len(locations)):
            if dis_map.get((i, j)) <= threshold:
                curlist = topology.get(i, [])
                curlist.append(j)
                topology[i] = curlist
                curlist = topology.get(j, [])
                curlist.append(i)
                topology[j] = curlist
    return topology


def _dfs(topology, cur, visited):
    if cur in visited:
        return
    visited.add(cur)
    for _next in topology.get(cur):
        _dfs(topology, _next, visited)


def simulate_device_networks(devices: dict[str, VirtualEntity]):
    """Simulate device networks."""
    dims = [30, 50]  # meters

    # locations = []
    hub_location = [0 for _ in dims]
    for device in devices.values():
        location = []
        for dim in dims:
            location.append(random.uniform(-dim / 2, dim / 2))
        # locations.append(location)
        dis_to_hub = _dis(hub_location, location)
        owd = 1.4054 * math.exp(0.0301 * dis_to_hub) / 1000  # s
        device.owd = owd


# def main():
#     """Main function for network plugin."""
#     parser = argparse.ArgumentParser()
#     parser.add_argument("-d", "--dimensions", type=list, default=[2, 3])

#     args = parser.parse_args()

#     device_no = 1
#     for dim in args.dimensions:
#         device_no *= dim

#     locations = []
#     for _ in range(device_no):
#         location = []
#         for dim in args.dimensions:
#             location.append(random.uniform(0, dim))
#         locations.append(location)

#     threshold, dis_map = _get_threshold(locations, args.dimensions)
#     topology = _get_topology(locations, dis_map, threshold * 1.1)

#     while True:
#         visited = set()
#         _dfs(topology, 0, visited)
#         # print("len visited: ", len(visited))
#         if len(visited) < device_no:
#             threshold *= 1.5
#             topology = _get_topology(locations, dis_map, threshold)
#         else:
#             break
#     # print(topology)

#     # owd=1.4054*e^(0.0301*d)


# if __name__ == "__main__":
#     main()
