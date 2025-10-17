# Configuration

This document provides detailed information about configuring the DayBetter Services integration.

## Initial Setup

### Step 1: Add Integration

1. Open Home Assistant
2. Navigate to **Settings** > **Devices & Services**
3. Click **Add Integration**
4. Search for "DayBetter Services"
5. Click on the integration to begin setup

### Step 2: Authentication

1. Enter your DayBetter user code
2. Click **Submit**
3. The integration will authenticate with the DayBetter API
4. Upon successful authentication, the integration will be added

### Step 3: Device Discovery

After successful authentication, the integration will:
1. Fetch your device list from the DayBetter API
2. Create entities for each discovered device
3. Attempt to establish MQTT connection for real-time updates

## Configuration Parameters

### Required Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `user_code` | Your DayBetter user code for API authentication | `ABC123` |

### Auto-Generated Parameters

| Parameter | Description | Notes |
|-----------|-------------|-------|
| `token` | API authentication token | Automatically generated during setup |

## Configuration Flow

The integration uses Home Assistant's config flow system:

1. **User Step**: Enter user code
2. **Validation**: Authenticate with DayBetter API
3. **Token Generation**: Generate and store authentication token
4. **Device Discovery**: Fetch and store device information
5. **Completion**: Create config entry and setup platforms

## Reconfiguration

To reconfigure the integration:

1. Go to **Settings** > **Devices & Services**
2. Find the DayBetter Services integration
3. Click the three dots menu
4. Select **Configure**
5. Follow the setup process again

## Multiple Configurations

The integration supports multiple configurations if you have multiple DayBetter accounts:

1. Each configuration requires a unique user code
2. Devices from different accounts will be managed separately
3. Each configuration has its own MQTT connection

## Configuration Validation

The integration validates configuration by:

1. **User Code Format**: Ensures the user code is not empty
2. **API Authentication**: Verifies the user code with DayBetter API
3. **Token Generation**: Ensures successful token generation
4. **Device Access**: Confirms access to device list

## Error Handling

### Common Configuration Errors

| Error | Description | Solution |
|-------|-------------|----------|
| `auth_failed` | Invalid user code | Verify user code is correct |
| `connection_error` | Cannot connect to API | Check internet connection |
| `invalid_format` | User code format error | Ensure user code is valid |

### Troubleshooting Configuration Issues

1. **Check User Code**: Verify the user code is correct and active
2. **Internet Connection**: Ensure stable internet connectivity
3. **API Status**: Check if DayBetter API is accessible
4. **Home Assistant Logs**: Review logs for detailed error information

## Advanced Configuration

### Custom API Endpoint

The integration uses the default DayBetter API endpoint. Custom endpoints are not currently supported.

### MQTT Configuration

MQTT configuration is automatically managed by the integration:

1. **Certificate Management**: Automatically downloads and manages certificates
2. **Connection Settings**: Uses DayBetter-provided connection parameters
3. **Reconnection**: Automatic reconnection on connection loss

### Device Filtering

Currently, all devices associated with your user code are imported. Device filtering is not available.

## Configuration Backup

To backup your configuration:

1. Export your Home Assistant configuration
2. The integration configuration is included in the export
3. Restore by importing the configuration

## Configuration Reset

To reset the integration configuration:

1. Remove the integration from **Devices & Services**
2. Clear any cached data
3. Re-add the integration with fresh configuration

## Best Practices

1. **Unique User Codes**: Use unique user codes for each account
2. **Regular Updates**: Keep the integration updated
3. **Monitor Logs**: Regularly check logs for issues
4. **Test Connectivity**: Verify API connectivity before setup
5. **Backup Configuration**: Regular backup of configuration

## Security Considerations

1. **Token Storage**: Tokens are stored securely in Home Assistant
2. **API Communication**: All API communication uses HTTPS
3. **MQTT Security**: MQTT connections use TLS encryption
4. **User Code Protection**: Keep your user code secure and private
