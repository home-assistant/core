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

from typing import Any

import pyroute2
from python_otbr_api.tlv_parser import MeshcopTLVType

from homeassistant.components.thread.dataset_store import async_get_store
from homeassistant.components.thread.discovery import (
    async_read_zeroconf_cache,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components import zeroconf


def _get_possible_thread_routes() -> tuple[dict[str, Any], dict[str, Any]]:
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
    return routes, reverse_routes


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for all known thread networks."""

    networks = {}

    # Start with all networks that HA knows about
    store = await async_get_store(hass)
    for record in store.datasets.values():
        network = networks.setdefault(
            record.extended_pan_id,
            {"name": record.network_name, "routers": {}, "prefixes": set()},
        )
        if mlp := record.dataset.get(MeshcopTLVType.MESHLOCALPREFIX):
            network.setdefault("prefixes", set()).add(
                f"{mlp[0:4]}:{mlp[4:8]}:{mlp[8:12]}:{mlp[12:16]}"
            )

    # Find all routes currently act that might be thread related, so we can match them to
    # border routers as we process the zeroconf data.
    routes, reverse_routes = await hass.async_add_executor_job(
        _get_possible_thread_routes
    )

    aiozc = await zeroconf.async_get_async_instance(hass)
    for data in async_read_zeroconf_cache(aiozc):
        network = networks.setdefault(
            data.extended_pan_id,
            {"name": data.network_name, "routers": {}, "prefixes": set()},
        )
        router = network["routers"][data.server] = {
            "server": data.server,
            "addresses": data.addresses,
            "thread_version": data.thread_version,
            "model": data.model_name,
            "vendor": data.vendor_name,
            "routes": {},
        }

        # For every address this border router hass, see if we have seen
        # it in the route table as a via - these are the routes its
        # announcing via RA
        for address in data.addresses:
            if address in routes:
                router["routes"].update(routes[address])

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
                network["unexpected-routers"] = ghosts

    return {
        "networks": networks,
    }
