# Device Discovery

This skill covers implementing device discovery methods for Home Assistant integrations.

## When to Use

- Adding automatic device discovery
- Implementing zeroconf, DHCP, SSDP, or Bluetooth discovery
- Updating device network information dynamically

## Discovery Methods

| Method | Use Case |
|--------|----------|
| `zeroconf` | mDNS/Bonjour services |
| `dhcp` | MAC address or hostname patterns |
| `ssdp` | UPnP devices |
| `bluetooth` | Bluetooth LE devices |
| `usb` | USB devices |

## Zeroconf Discovery

### manifest.json

```json
{
  "zeroconf": [
    {
      "type": "_mydevice._tcp.local.",
      "name": "mydevice*"
    }
  ]
}
```

Or simple form:

```json
{
  "zeroconf": ["_mydevice._tcp.local."]
}
```

### Config Flow Handler

```python
from homeassistant.components.zeroconf import ZeroconfServiceInfo

async def async_step_zeroconf(
    self, discovery_info: ZeroconfServiceInfo
) -> ConfigFlowResult:
    """Handle zeroconf discovery."""
    # Extract device identifier
    serial = discovery_info.properties.get("serialno")
    if not serial:
        return self.async_abort(reason="no_serial")

    # Set unique ID and check for existing entry
    await self.async_set_unique_id(serial)
    self._abort_if_unique_id_configured(
        updates={CONF_HOST: str(discovery_info.host)}
    )

    # Store discovery info for later steps
    self._discovered_host = str(discovery_info.host)
    self._discovered_name = discovery_info.name.removesuffix("._mydevice._tcp.local.")

    # Show confirmation form
    self.context["title_placeholders"] = {"name": self._discovered_name}
    return await self.async_step_discovery_confirm()

async def async_step_discovery_confirm(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    """Confirm discovery."""
    if user_input is not None:
        return self.async_create_entry(
            title=self._discovered_name,
            data={CONF_HOST: self._discovered_host},
        )

    return self.async_show_form(
        step_id="discovery_confirm",
        description_placeholders={"name": self._discovered_name},
    )
```

### Using Async Zeroconf

```python
from homeassistant.components import zeroconf

aiozc = await zeroconf.async_get_async_instance(hass)
```

## DHCP Discovery

### manifest.json

```json
{
  "dhcp": [
    {
      "macaddress": "AA:BB:CC:*",
      "hostname": "mydevice*"
    }
  ]
}
```

### Config Flow Handler

```python
from homeassistant.components.dhcp import DhcpServiceInfo

async def async_step_dhcp(
    self, discovery_info: DhcpServiceInfo
) -> ConfigFlowResult:
    """Handle DHCP discovery."""
    await self.async_set_unique_id(format_mac(discovery_info.macaddress))
    self._abort_if_unique_id_configured(
        updates={CONF_HOST: discovery_info.ip}
    )

    self._discovered_host = discovery_info.ip
    return await self.async_step_discovery_confirm()
```

## SSDP Discovery

### manifest.json

```json
{
  "ssdp": [
    {
      "st": "urn:schemas-upnp-org:device:MyDevice:1"
    }
  ]
}
```

### Config Flow Handler

```python
from homeassistant.components.ssdp import SsdpServiceInfo

async def async_step_ssdp(
    self, discovery_info: SsdpServiceInfo
) -> ConfigFlowResult:
    """Handle SSDP discovery."""
    serial = discovery_info.upnp.get("serialNumber")
    if not serial:
        return self.async_abort(reason="no_serial")

    await self.async_set_unique_id(serial)
    self._abort_if_unique_id_configured(
        updates={CONF_HOST: discovery_info.ssdp_location}
    )

    return await self.async_step_discovery_confirm()
```

### SSDP Callbacks in Runtime

```python
from homeassistant.components import ssdp

entry.async_on_unload(
    ssdp.async_register_callback(
        hass,
        _async_discovered_device,
        {"st": "urn:schemas-upnp-org:device:ZonePlayer:1"},
    )
)
```

## Bluetooth Discovery

### manifest.json

```json
{
  "bluetooth": [
    {
      "service_uuid": "0000180f-0000-1000-8000-00805f9b34fb"
    }
  ],
  "dependencies": ["bluetooth_adapters"]
}
```

For connectable devices:

```json
{
  "bluetooth": [
    {
      "service_uuid": "0000180f-0000-1000-8000-00805f9b34fb",
      "connectable": true
    }
  ]
}
```

### Config Flow Handler

```python
from homeassistant.components.bluetooth import BluetoothServiceInfo

async def async_step_bluetooth(
    self, discovery_info: BluetoothServiceInfo
) -> ConfigFlowResult:
    """Handle Bluetooth discovery."""
    await self.async_set_unique_id(discovery_info.address)
    self._abort_if_unique_id_configured()

    self._discovered_device = discovery_info
    return await self.async_step_bluetooth_confirm()
```

### Bluetooth Runtime Callbacks

```python
from homeassistant.components import bluetooth

entry.async_on_unload(
    bluetooth.async_register_callback(
        hass,
        _async_discovered_device,
        {"service_uuid": "example_uuid"},
        bluetooth.BluetoothScanningMode.ACTIVE,
    )
)
```

### Bluetooth Connection Guidelines

- Never reuse `BleakClient` instances
- Use 10+ second timeouts
- Use shared scanner instance:

```python
scanner = bluetooth.async_get_scanner(hass)
```

## Dynamic IP Updates

Use discovery to update dynamic IP addresses:

```python
self._abort_if_unique_id_configured(
    updates={CONF_HOST: discovery_info.host}
)
```

This updates the existing entry's host without creating a new entry.

## strings.json for Discovery

```json
{
  "config": {
    "step": {
      "discovery_confirm": {
        "title": "Discovered device",
        "description": "Do you want to set up {name}?"
      }
    },
    "abort": {
      "no_serial": "Device did not provide serial number",
      "already_configured": "Device is already configured"
    }
  }
}
```

## Related Skills

- `config-flow` - Config flow basics
- `async-programming` - Async discovery handlers
- `quality-scale` - Discovery is a Gold requirement
