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

import asyncio
from typing import Any

import pyroute2
from python_otbr_api.tlv_parser import MeshcopTLVType

from homeassistant.components.thread.dataset_store import async_get_store
from homeassistant.components.thread.discovery import (
    ThreadRouterDiscovery,
    ThreadRouterDiscoveryData,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    # Build a list of possible thread routes
    # Right now, this is ipv6 /64's that have a gateway
    # We cross reference with zerconf data to confirm which via's are known border routers
    routes = {}
    reverse_routes = {}

    with pyroute2.NDB() as ndb:
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
                "is-nexthop": record.nh_gateway is not None,
            }
            reverse_routes.setdefault(record.dst, set()).add(gateway)

    networks = {}

    def router_discovered(name: str, data: ThreadRouterDiscoveryData):
        network = networks.setdefault(
            data.extended_pan_id, {"name": data.network_name, "routers": {}}
        )
        router = network["routers"][data.server] = {
            "server": data.server,
            "addresses": data.addresses,
            "thread_version": data.thread_version,
            "model": data.model_name,
            "vendor": data.vendor_name,
            "routes": {},
        }

        for address in data.addresses:
            if address in routes:
                router["routes"] = routes[address]

    discovery = ThreadRouterDiscovery(hass, router_discovered, lambda str: None)
    await discovery.async_start()
    await asyncio.sleep(5)
    await discovery.async_stop()

    for network in networks.values():
        network["prefixes"] = prefixes = set()
        routers = set()

        for router in network["routers"].values():
            prefixes.update(router["routes"].keys())
            routers.update(router["addresses"])

        # Find any stale routes that we can't map to a meshcop record.
        for prefix in prefixes:
            if ghosts := reverse_routes[prefix] - routers:
                network["unexpected-routers"] = ghosts

    store = await async_get_store(hass)
    for record in store.datasets.values():
        network = networks.setdefault(
            record.extended_pan_id, {"name": record.network_name, "routers": {}}
        )
        if mlp := record.dataset.get(MeshcopTLVType.MESHLOCALPREFIX):
            network.setdefault("prefixes", set()).add(
                f"{mlp[0:4]}:{mlp[4:8]}:{mlp[8:12]}:{mlp[12:16]}"
            )

    return {
        "networks": networks,
    }
