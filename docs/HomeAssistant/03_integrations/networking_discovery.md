---
title: "Networking and discovery"
sidebar_label: "Networking and discovery"
---

Some integrations may need to discover devices on the network via [mDNS/Zeroconf](https://en.wikipedia.org/wiki/Zero-configuration_networking), [SSDP](https://en.wikipedia.org/wiki/Simple_Service_Discovery_Protocol), or another method once they have been enabled.  The primary use case is to find devices that do not have a known fixed IP Address or for integrations that can dynamically add and remove any number of compatible discoverable devices.

Home Assistant has built-in helpers to support mDNS/Zeroconf and SSDP. If your integration uses another discovery method that needs to determine which network interfaces to use to broadcast traffic, the [Network](https://www.home-assistant.io/integrations/network/) integration provides a helper API to access the user's interface preferences.


## mDNS/Zeroconf

Home Assistant uses the [python-zeroconf](https://github.com/python-zeroconf/python-zeroconf) package for mDNS support. As running multiple mDNS implementations on a single host is not recommended, Home Assistant provides internal helper APIs to access the running `Zeroconf` and `AsyncZeroconf` instances.

Before using these helpers, be sure to add `zeroconf` to `dependencies` in your integration's [`manifest.json`](creating_integration_manifest.md)

### Obtaining the `AsyncZeroconf` object

```python
from homeassistant.components import zeroconf

...
aiozc = await zeroconf.async_get_async_instance(hass)

```

### Obtaining the `Zeroconf` object

```python
from homeassistant.components import zeroconf

...
zc = await zeroconf.async_get_instance(hass)

```

### Using the `AsyncZeroconf` and `Zeroconf` objects

`python-zeroconf` provides examples on how to use both objects [examples](https://github.com/jstasiak/python-zeroconf/tree/master/examples).

## SSDP

Home Assistant provides built-in discovery via SSDP.

Before using these helpers, be sure to add `ssdp` to `dependencies` in your integration's [`manifest.json`](creating_integration_manifest.md)

### Obtaining the list of discovered devices

The list of discovered SSDP devices can be obtained using the following built-in
helper APIs. The SSDP integration provides the following helper APIs to lookup existing
SSDP discoveries from the cache: `ssdp.async_get_discovery_info_by_udn_st`, `ssdp.async_get_discovery_info_by_st`, `ssdp.async_get_discovery_info_by_udn`

### Looking up a specific device

The `ssdp.async_get_discovery_info_by_udn_st` API returns a single `discovery_info`
or `None` when provided an `SSDP`, `UDN` and `ST`.

```
from homeassistant.components import ssdp

...

discovery_info = await ssdp.async_get_discovery_info_by_udn_st(hass, udn, st)
```

### Looking up devices by `ST`

If you want to look for a specific type of discovered devices, calling
`ssdp.async_get_discovery_info_by_st` will return a list of all discovered devices that
match the `SSDP` `ST`. The below example returns a list of discovery info for every
Sonos player discovered on the network.

```
from homeassistant.components import ssdp

...

discovery_infos = await ssdp.async_get_discovery_info_by_st(hass, "urn:schemas-upnp-org:device:ZonePlayer:1")
for discovery_info in discovery_infos:
  ...

```


### Looking up devices by `UDN`

If you want to see a list of the services provided by a specific `UDN`, calling
`ssdp.async_get_discovery_info_by_udn` will return a list of all discovered devices that
match the `UPNP` `UDN`.

```
from homeassistant.components import ssdp

...

discovery_infos = await ssdp.async_get_discovery_info_by_udn(hass, udn)
for discovery_info in discovery_infos:
  ...

```

### Subscribing to SSDP discoveries

Some integrations may need to know when a device is discovered right away. The SSDP integration provides a registration API to receive callbacks when a new device is discovered that matches specific key values. The same format for `ssdp` in [`manifest.json`](creating_integration_manifest.md) is used for matching.

The function `ssdp.async_register_callback` is provided to enable this ability. The function returns a callback that will cancel the registration when called.

The below example shows registering to get callbacks when a Sonos player is seen
on the network.

```
from homeassistant.components import ssdp

...

entry.async_on_unload(
    ssdp.async_register_callback(
        hass, _async_discovered_player, {"st": "urn:schemas-upnp-org:device:ZonePlayer:1"}
    )
)
```

The below example shows registering to get callbacks when the `x-rincon-bootseq` header is present.

```
from homeassistant.components import ssdp
from homeassistant.const import MATCH_ALL

...

entry.async_on_unload(
    ssdp.async_register_callback(
        hass, _async_discovered_player, {"x-rincon-bootseq": MATCH_ALL}
    )
)
```


## Network

For integrations that use a discovery method that is not built-in and need to access the user's network adapter configuration, the following helper API should be used.


```python
from homeassistant.components import network

...
adapters = await network.async_get_adapters(hass)
```

### Example `async_get_adapters` data structure

```python
[
    {   
        "auto": True,
        "default": False,
        "enabled": True,
        "ipv4": [],
        "ipv6": [
            {   
                "address": "2001:db8::",
                "network_prefix": 8,
                "flowinfo": 1,
                "scope_id": 1,
            }
        ],
        "name": "eth0",
    },
    {
        "auto": True,
        "default": False,
        "enabled": True,
        "ipv4": [{"address": "192.168.1.5", "network_prefix": 23}],
        "ipv6": [],
        "name": "eth1",
    },
    {
        "auto": False,
        "default": False,
        "enabled": False,
        "ipv4": [{"address": "169.254.3.2", "network_prefix": 16}],
        "ipv6": [],
        "name": "vtun0",
    },
]
```

### Obtaining the IP Network from an adapter

```python
from ipaddress import ip_network
from homeassistant.components import network

...

adapters = await network.async_get_adapters(hass)

for adapter in adapters:
    for ip_info in adapter["ipv4"]:
        local_ip = ip_info["address"]
        network_prefix = ip_info["network_prefix"]
        ip_net = ip_network(f"{local_ip}/{network_prefix}", False)
```

## USB

The USB integration discovers new USB devices at startup, when the integrations page is accessed, and when they are plugged in if the underlying system has support for `pyudev`.

### Checking if a specific adapter is plugged in

Call the `async_is_plugged_in` API to check if a specific adapter is on the system.

```python
from homeassistant.components import usb

...

if not usb.async_is_plugged_in(hass, {"serial_number": "A1234", "manufacturer": "xtech"}):
   raise ConfigEntryNotReady("The USB device is missing")

```

### Knowing when to look for new compatible USB devices

Call the `async_register_scan_request_callback` API to request a callback when new compatible USB devices may be available.

```python
from homeassistant.components import usb
from homeassistant.core import callback

...

@callback
def _async_check_for_usb() -> None:
    """Check for new compatible bluetooth USB adapters."""

entry.async_on_unload(
    bluetooth.async_register_scan_request_callback(hass, _async_check_for_usb)
)
```
