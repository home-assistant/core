"""Diagnostics support for Thread networks.

When triaging Matter and HomeKit issues you often need to check for problems with the Thread network.

This report helps spot and rule out:

* Is the users border router visible at all?
* Is the border router actually announcing any routes? The user could have a network boundary like
  VLANs or WiFi isolation that is blocking the RA packets.
* Alternatively, if user isn't on HAOS they could have accept_ra_rt_info_max_plen set incorrectly.
* Are there any bogus routes that could be interfering. If routes don't expire they can build up.
  When you have 10 routes and only 2 border routers something has gone wrong.

This does not do any connectivity checks. So user could have all their border routers visible, but
some of their thread accessories can't be pinged, but it's still a thread problem.
"""

from __future__ import annotations

from typing import Any, TypedDict

from pyroute2 import NDB  # pylint: disable=no-name-in-module
from python_otbr_api.tlv_parser import MeshcopTLVType

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .dataset_store import async_get_store
from .discovery import async_read_zeroconf_cache


class Neighbour(TypedDict):
    """A neighbour cache entry (ip neigh)."""

    lladdr: str
    state: int
    probes: int


class Route(TypedDict):
    """A route table entry (ip -6 route)."""

    metrics: int
    priority: int
    is_nexthop: bool


class Router(TypedDict):
    """A border router."""

    server: str | None
    addresses: list[str]
    neighbours: dict[str, Neighbour]
    thread_version: str | None
    model: str | None
    vendor: str | None
    routes: dict[str, Route]


class Network(TypedDict):
    """A thread network."""

    name: str | None
    routers: dict[str, Router]
    prefixes: set[str]
    unexpected_routers: set[str]


def _get_possible_thread_routes() -> (
    tuple[dict[str, dict[str, Route]], dict[str, set[str]]]
):
    # Build a list of possible thread routes
    # Right now, this is ipv6 /64's that have a gateway
    # We cross reference with zerconf data to confirm which via's are known border routers
    routes: dict[str, dict[str, Route]] = {}
    reverse_routes: dict[str, set[str]] = {}

    with NDB() as ndb:
        for record in ndb.routes:
            # Limit to IPV6 routes
            if record.family != 10:
                continue
            # Limit to /64 prefixes
            if record.dst_len != 64:
                continue
            # Limit to routes with a via
            if not record.gateway and not record.nh_gateway:
                continue
            gateway = record.gateway or record.nh_gateway
            route = routes.setdefault(gateway, {})
            route[record.dst] = {
                "metrics": record.metrics,
                "priority": record.priority,
                # NM creates "nexthop" routes - a single route with many via's
                # Kernel creates many routes with a single via
                "is_nexthop": record.nh_gateway is not None,
            }
            reverse_routes.setdefault(record.dst, set()).add(gateway)
    return routes, reverse_routes


def _get_neighbours() -> dict[str, Neighbour]:
    neighbours: dict[str, Neighbour] = {}

    with NDB() as ndb:
        for record in ndb.neighbours:
            neighbours[record.dst] = {
                "lladdr": record.lladdr,
                "state": record.state,
                "probes": record.probes,
            }

    return neighbours


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for all known thread networks."""

    networks: dict[str, Network] = {}

    # Start with all networks that HA knows about
    store = await async_get_store(hass)
    for record in store.datasets.values():
        if not record.extended_pan_id:
            continue
        network = networks.setdefault(
            record.extended_pan_id,
            {
                "name": record.network_name,
                "routers": {},
                "prefixes": set(),
                "unexpected_routers": set(),
            },
        )
        if mlp := record.dataset.get(MeshcopTLVType.MESHLOCALPREFIX):
            network["prefixes"].add(f"{mlp[0:4]}:{mlp[4:8]}:{mlp[8:12]}:{mlp[12:16]}")

    # Find all routes currently act that might be thread related, so we can match them to
    # border routers as we process the zeroconf data.
    routes, reverse_routes = await hass.async_add_executor_job(
        _get_possible_thread_routes
    )

    # Find all neighbours
    neighbours = await hass.async_add_executor_job(_get_neighbours)

    aiozc = await zeroconf.async_get_async_instance(hass)
    for data in async_read_zeroconf_cache(aiozc):
        if not data.extended_pan_id:
            continue

        network = networks.setdefault(
            data.extended_pan_id,
            {
                "name": data.network_name,
                "routers": {},
                "prefixes": set(),
                "unexpected_routers": set(),
            },
        )

        if not data.server:
            continue

        router = network["routers"][data.server] = {
            "server": data.server,
            "addresses": data.addresses or [],
            "neighbours": {},
            "thread_version": data.thread_version,
            "model": data.model_name,
            "vendor": data.vendor_name,
            "routes": {},
        }

        # For every address this border router hass, see if we have seen
        # it in the route table as a via - these are the routes its
        # announcing via RA
        if data.addresses:
            for address in data.addresses:
                if address in routes:
                    router["routes"].update(routes[address])

                if address in neighbours:
                    router["neighbours"][address] = neighbours[address]

        network["prefixes"].update(router["routes"].keys())

    # Find unexpected via's.
    # Collect all router addresses and then for each prefix, find via's that aren't
    # a known router for that prefix.
    for network in networks.values():
        routers = set()

        for router in network["routers"].values():
            routers.update(router["addresses"])

        for prefix in network["prefixes"]:
            if prefix not in reverse_routes:
                continue
            if ghosts := reverse_routes[prefix] - routers:
                network["unexpected_routers"] = ghosts

    return {
        "networks": networks,
    }
