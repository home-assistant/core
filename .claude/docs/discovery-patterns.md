# Discovery Patterns

## Manifest Configuration

Add discovery method to `manifest.json`:
```json
{
  "zeroconf": ["_mydevice._tcp.local."],
  "ssdp": [{"st": "urn:schemas-upnp-org:device:Basic:1"}],
  "dhcp": [{"hostname": "mydevice*", "macaddress": "AABBCC*"}],
  "bluetooth": [{"service_uuid": "example-uuid"}]
}
```

## Zeroconf/mDNS

Use async instances:
```python
aiozc = await zeroconf.async_get_async_instance(hass)
```

Config flow handler:
```python
async def async_step_zeroconf(
    self, discovery_info: ZeroconfServiceInfo
) -> ConfigFlowResult:
    """Handle zeroconf discovery."""
    await self.async_set_unique_id(discovery_info.properties["serialno"])
    self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

    self._discovered_host = discovery_info.host
    return await self.async_step_discovery_confirm()
```

## SSDP Discovery

Register callbacks with cleanup:
```python
entry.async_on_unload(
    ssdp.async_register_callback(
        hass, _async_discovered_device,
        {"st": "urn:schemas-upnp-org:device:ZonePlayer:1"}
    )
)
```

## DHCP Discovery

```python
async def async_step_dhcp(
    self, discovery_info: DhcpServiceInfo
) -> ConfigFlowResult:
    """Handle DHCP discovery."""
    await self.async_set_unique_id(
        format_mac(discovery_info.macaddress)
    )
    self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

    return await self.async_step_discovery_confirm()
```

## Bluetooth Integration

**Manifest dependencies**:
```json
{
  "dependencies": ["bluetooth_adapters"],
  "bluetooth": [
    {"service_uuid": "example-uuid", "connectable": true}
  ]
}
```

**Scanner usage** - always use shared instance:
```python
scanner = bluetooth.async_get_scanner()
entry.async_on_unload(
    bluetooth.async_register_callback(
        hass, _async_discovered_device,
        {"service_uuid": "example_uuid"},
        bluetooth.BluetoothScanningMode.ACTIVE
    )
)
```

**Connection handling**:
- Never reuse `BleakClient` instances
- Use 10+ second timeouts

```python
# Create fresh client each time
client = BleakClient(address)
async with client:
    await client.read_gatt_char(CHARACTERISTIC_UUID)
```

## Network Updates via Discovery

Use discovery to update dynamic IP addresses:
```python
self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})
```

This updates the host in the existing config entry if the device is already configured.

## USB Discovery

```json
{
  "usb": [
    {"vid": "10C4", "pid": "EA60", "description": "*MyDevice*"}
  ]
}
```

```python
async def async_step_usb(
    self, discovery_info: UsbServiceInfo
) -> ConfigFlowResult:
    """Handle USB discovery."""
    await self.async_set_unique_id(discovery_info.serial_number)
    self._abort_if_unique_id_configured()

    self._discovered_device = discovery_info.device
    return await self.async_step_discovery_confirm()
```
