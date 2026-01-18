# Device Discovery

This skill covers implementing device discovery methods for Home Assistant integrations.

## When to Use

- Adding automatic device discovery
- Implementing zeroconf, DHCP, SSDP, or Bluetooth discovery
- Updating device network information dynamically

## Device Discovery

- **Manifest Configuration**: Add discovery method (zeroconf, dhcp, etc.)
  ```json
  {
    "zeroconf": ["_mydevice._tcp.local."]
  }
  ```
- **Discovery Handler**: Implement appropriate `async_step_*` method:
  ```python
  async def async_step_zeroconf(self, discovery_info):
      """Handle zeroconf discovery."""
      await self.async_set_unique_id(discovery_info.properties["serialno"])
      self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})
  ```
- **Network Updates**: Use discovery to update dynamic IP addresses

## Network Discovery Implementation

- **Zeroconf/mDNS**: Use async instances
  ```python
  aiozc = await zeroconf.async_get_async_instance(hass)
  ```
- **SSDP Discovery**: Register callbacks with cleanup
  ```python
  entry.async_on_unload(
      ssdp.async_register_callback(
          hass, _async_discovered_device, 
          {"st": "urn:schemas-upnp-org:device:ZonePlayer:1"}
      )
  )
  ```

## Bluetooth Integration

- **Manifest Dependencies**: Add `bluetooth_adapters` to dependencies
- **Connectable**: Set `"connectable": true` for connection-required devices
- **Scanner Usage**: Always use shared scanner instance
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
- **Connection Handling**: Never reuse `BleakClient` instances, use 10+ second timeouts

## Related Skills

- `config-flow` - Config flow basics
- `async-programming` - Async discovery handlers
- `quality-scale` - Discovery is a Gold requirement
