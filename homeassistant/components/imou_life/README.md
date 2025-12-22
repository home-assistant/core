# Imou Life Integration

The Imou Life integration allows you to control and monitor Imou devices (cameras, sensors, etc.) through Home Assistant using the Imou Open Platform API.

## High-Level Description

This integration connects to the Imou cloud service to provide Home Assistant with access to your Imou devices. It supports device discovery, status monitoring, and control operations such as PTZ (Pan-Tilt-Zoom) movements and device restart.

The integration uses the Imou Open Platform API to authenticate and communicate with your devices. All communication is done through the cloud service, making it accessible from anywhere.

## Installation Instructions

### Prerequisites

Before installing this integration, you need to:

1. **Create an Imou Open Platform Account**
   - Visit [Imou Open Platform](https://open.imoulife.com/)
   - Register for a developer account
   - Create an application to obtain your `AppId` and `AppSecret`

2. **Get Your Credentials**
   - Log in to the Imou Open Platform dashboard
   - Navigate to your application settings
   - Copy your `AppId` and `AppSecret`

### Installation Steps

1. **Add Integration via UI**
   - Go to **Settings** > **Devices & Services**
   - Click **Add Integration**
   - Search for **Imou Life Official**
   - Click on the integration

2. **Configure the Integration**
   - Enter your `AppId` (Application ID)
   - Enter your `AppSecret` (Application Secret)
   - Select the appropriate API URL based on your region:
     - **Singapore**: `openapi-sg.easy4ip.com` (Default)
     - **Oregon**: `openapi-or.easy4ip.com`
     - **Frankfurt**: `openapi-fk.easy4ip.com`
     - **Hangzhou**: `openapi.lechange.cn`
   - Click **Submit**

3. **Verify Installation**
   - The integration will authenticate with the Imou API
   - If successful, your devices will be automatically discovered
   - Check the **Devices & Services** page to see your Imou devices

### Configuration Parameters

- **AppId** (Required): Your Imou Open Platform Application ID
- **AppSecret** (Required): Your Imou Open Platform Application Secret
- **API URL** (Required): The API endpoint URL for your region

### Options Configuration

After installation, you can configure additional options:

- **Rotation Duration**: The duration (in milliseconds) for PTZ rotation operations
  - Range: 100-10000 milliseconds
  - Default: 500 milliseconds

To configure options:
1. Go to **Settings** > **Devices & Services**
2. Find your Imou Life integration
3. Click on the integration card
4. Click **Options** (or the three dots menu)
5. Adjust the rotation duration as needed
6. Click **Submit**

## Removal Instructions

### Removing the Integration

To completely remove the Imou Life integration from Home Assistant:

1. **Remove via UI**
   - Go to **Settings** > **Devices & Services**
   - Find the **Imou Life Official** integration
   - Click on the integration card
   - Click the three dots menu (⋮) in the top right
   - Select **Delete**
   - Confirm the deletion

2. **Clean Up (Optional)**
   - After removal, all associated devices and entities will be automatically removed
   - If you want to reinstall later, you can use the same credentials

### What Gets Removed

When you remove the integration:
- All Imou devices are removed from the device registry
- All entities (buttons, sensors, etc.) are removed
- Configuration entry is deleted
- No data is retained (you can re-add the integration with the same credentials)

### Re-adding the Integration

If you want to re-add the integration after removal:
- Simply follow the installation steps again
- Use the same `AppId` and `AppSecret`
- Your devices will be rediscovered automatically

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify your `AppId` and `AppSecret` are correct
   - Check that your application is active in the Imou Open Platform
   - Ensure you're using the correct API URL for your region

2. **Devices Not Appearing**
   - Wait a few moments for device discovery to complete
   - Check the Home Assistant logs for any error messages
   - Verify your devices are online in the Imou app

3. **PTZ Controls Not Working**
   - Check that your device supports PTZ operations
   - Verify the rotation duration is set appropriately (100-10000ms)
   - Ensure the device is online and accessible

### Getting Help

- **Documentation**: [Imou Open Platform Documentation](https://open.imoulife.com/book/guide/haDev.html)
- **Issue Tracker**: [GitHub Issues](https://github.com/Imou-OpenPlatform/Imou-Home-Assistant/issues)
- **Home Assistant Community**: [Home Assistant Forum](https://community.home-assistant.io/)

## Supported Devices

This integration supports all devices that are compatible with the Imou Open Platform API, including:
- IP Cameras
- PTZ Cameras
- Sensors
- Other Imou-compatible devices

## Data Update Interval

The integration polls the Imou cloud service every 60 seconds to update device status. This interval is automatically managed and cannot be configured by the user.

## Security Notes

- Your `AppSecret` is stored securely in Home Assistant's configuration
- All communication with the Imou API is encrypted
- Credentials are never exposed in logs or diagnostics

