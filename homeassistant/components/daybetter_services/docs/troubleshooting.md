# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the DayBetter Services integration.

## Common Issues

### Authentication Problems

#### Issue: "Authentication failed" Error
**Symptoms:**
- Integration setup fails
- Error message: "Authentication failed. Please check your user code."

**Possible Causes:**
- Invalid or expired user code
- Network connectivity issues
- DayBetter API service issues

**Solutions:**
1. **Verify User Code**:
   - Check that your user code is correct
   - Ensure the user code is not expired
   - Verify the user code is active in the DayBetter app

2. **Network Issues**:
   - Test internet connectivity
   - Check if DayBetter API is accessible
   - Try from a different network if possible

3. **API Service Issues**:
   - Check DayBetter service status
   - Wait and retry if service is down
   - Contact DayBetter support if issues persist

#### Issue: "Connection error" During Setup
**Symptoms:**
- Setup fails with connection error
- Cannot reach DayBetter API

**Solutions:**
1. **Network Diagnostics**:
   ```bash
   # Test connectivity to DayBetter API
   ping a.dbiot.org
   curl -I https://a.dbiot.org/daybetter/hass/api/v1.0/
   ```

2. **Firewall/Proxy Issues**:
   - Check firewall settings
   - Configure proxy if needed
   - Ensure HTTPS traffic is allowed

3. **DNS Issues**:
   - Try different DNS servers
   - Clear DNS cache
   - Check DNS resolution

### Device Discovery Issues

#### Issue: No Devices Appearing
**Symptoms:**
- Integration loads successfully
- No devices are discovered
- Empty device list

**Solutions:**
1. **Manual Refresh**:
   ```yaml
   service: daybetter_services.refresh_devices
   ```

2. **Check Device Association**:
   - Verify devices are associated with your user code
   - Check device status in DayBetter app
   - Ensure devices are online

3. **API Response Check**:
   - Enable debug logging
   - Check logs for API response details
   - Verify API token is valid

#### Issue: Partial Device Discovery
**Symptoms:**
- Some devices appear, others don't
- Inconsistent device discovery

**Solutions:**
1. **Device Status Check**:
   - Verify all devices are online
   - Check device compatibility
   - Ensure devices are properly configured

2. **API Limits**:
   - Check if API rate limits are exceeded
   - Wait and retry
   - Contact DayBetter support

### MQTT Connection Issues

#### Issue: MQTT Connection Failed
**Symptoms:**
- Devices work but no real-time updates
- MQTT connection errors in logs
- Certificate download failures

**Solutions:**
1. **Manual MQTT Reconnection**:
   ```yaml
   service: daybetter_services.trigger_mqtt_connection
   ```

2. **Certificate Issues**:
   - Check certificate download logs
   - Verify certificate validity
   - Clear certificate cache if needed

3. **Network Issues**:
   - Test MQTT broker connectivity
   - Check firewall settings for MQTT ports
   - Verify TLS/SSL configuration

#### Issue: MQTT Disconnections
**Symptoms:**
- Frequent MQTT disconnections
- Intermittent real-time updates
- Connection timeout errors

**Solutions:**
1. **Network Stability**:
   - Check network stability
   - Test with wired connection
   - Monitor network latency

2. **MQTT Configuration**:
   - Check MQTT broker settings
   - Verify connection parameters
   - Adjust timeout settings if possible

### Device Control Issues

#### Issue: Device Control Not Working
**Symptoms:**
- Devices appear but commands don't work
- Control commands fail
- No response from devices

**Solutions:**
1. **Device Status**:
   - Check if device is online
   - Verify device is not in error state
   - Test control from DayBetter app

2. **API Token**:
   - Verify API token is valid
   - Try reconfiguring integration
   - Check token expiration

3. **Network Issues**:
   - Test API connectivity
   - Check for network timeouts
   - Verify HTTPS communication

#### Issue: Delayed Device Response
**Symptoms:**
- Commands work but with delay
- Slow device response
- Status updates are delayed

**Solutions:**
1. **Network Performance**:
   - Check network latency
   - Test from different network
   - Monitor bandwidth usage

2. **API Performance**:
   - Check DayBetter API status
   - Monitor API response times
   - Contact DayBetter support if needed

## Debugging

### Enable Debug Logging

Add this to your `configuration.yaml`:

```yaml
logger:
  logs:
    homeassistant.components.daybetter_services: debug
```

### Log Analysis

Look for these log patterns:

#### Successful Operations
```
DayBetter auth OK
Fetched devices: [...]
MQTT connection established
Device control successful
```

#### Error Patterns
```
Authentication failed: ...
Failed to fetch devices: ...
MQTT connection failed: ...
Device control failed: ...
Certificate download failed: ...
```

### Common Log Messages

| Log Message | Meaning | Action |
|-------------|---------|--------|
| `DayBetter auth OK` | Authentication successful | Normal operation |
| `Failed to fetch devices` | API communication issue | Check network/API |
| `MQTT connection failed` | MQTT connectivity issue | Check MQTT settings |
| `Device control failed` | Control command failed | Check device status |
| `Certificate download failed` | SSL certificate issue | Check certificate URL |

## Performance Issues

### Slow Integration Startup
**Symptoms:**
- Long startup time
- Delayed device discovery

**Solutions:**
1. **Network Optimization**:
   - Use wired connection
   - Optimize network settings
   - Check DNS resolution speed

2. **System Resources**:
   - Check Home Assistant system resources
   - Monitor CPU and memory usage
   - Optimize Home Assistant configuration

### High CPU Usage
**Symptoms:**
- High CPU usage by integration
- System performance degradation

**Solutions:**
1. **MQTT Optimization**:
   - Check MQTT message frequency
   - Optimize MQTT settings
   - Monitor MQTT connection health

2. **API Calls**:
   - Check API call frequency
   - Optimize polling intervals
   - Monitor API response times

## System Requirements

### Minimum Requirements
- Home Assistant 2023.1.0+
- 100MB free disk space
- Stable internet connection
- Python 3.10+

### Recommended Requirements
- Home Assistant 2023.12.0+
- 500MB free disk space
- High-speed internet connection
- Python 3.11+

## Getting Help

### Before Seeking Help

1. **Check Documentation**: Review this troubleshooting guide
2. **Enable Debug Logging**: Capture detailed logs
3. **Test Basic Functionality**: Verify network and API connectivity
4. **Gather Information**: Collect relevant system information

### Information to Provide

When seeking help, provide:

1. **System Information**:
   - Home Assistant version
   - Integration version
   - Operating system details

2. **Error Details**:
   - Complete error messages
   - Debug logs
   - Steps to reproduce

3. **Configuration**:
   - Integration configuration
   - Network setup
   - Device information

### Support Channels

1. **Home Assistant Community**: For general integration issues
2. **DayBetter Support**: For API or service issues
3. **GitHub Issues**: For bug reports and feature requests

## Prevention

### Best Practices

1. **Regular Updates**: Keep integration and Home Assistant updated
2. **Monitor Logs**: Regular log review for issues
3. **Network Maintenance**: Ensure stable network connectivity
4. **Backup Configuration**: Regular configuration backups
5. **Test Changes**: Test changes in development environment

### Monitoring

1. **Integration Health**: Regular health checks
2. **Device Status**: Monitor device online status
3. **API Connectivity**: Test API connectivity regularly
4. **MQTT Connection**: Monitor MQTT connection health
