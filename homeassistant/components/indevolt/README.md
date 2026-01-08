# Indevolt integration for Home Assistant

A Home Assistant custom integration to monitor and control [Indevolt](https://www.indevolt.com/) devices.


## Prerequisites
- [ ] Home Assistant has been installed according to the [official installation guide](https://www.home-assistant.io/installation/).
- [ ] The Indevolt device and Home Assistant server are on the **same local network**.
- [ ] The Indevolt device is powered on and has obtained an **IP address**.
  - Query via router’s management list;
  - Check in INDEVOLT App device settings;
  - Obtain IP via UDP broadcast:
    1. Ensure the device's WiFi network and computer are on the same local area network.
    2. Open a network debugging tool.
    3. Select UDP protocol.
    4. Select Local Host Addr.
    5. Set Local Host Post to 10000.
    6. Click Open.
    7. Configure Remote with broadcast address and port: 255.255.255.255:8099.
    8. Enter AT command in message box: AT+IGDEVICEIP.
    9. Click Send.
    10. INDEVOLT devices on the same network will respond with their IP address and serial number (SN).  
    <img width="200" alt="1set_udp" src="https://github.com/user-attachments/assets/68674988-fc59-438e-b703-548eff6167d7" />

    <img width="800" alt="2obtain_ip" src="https://github.com/user-attachments/assets/027b3e69-81b4-4894-bd7f-ca5b5b204ceb" />

- [ ] Ensure that the Indevolt device **API function is enabled**. This integration only supports OpenData HTTP unencrypted mode.
<img width="800" alt="3http_mode" src="https://github.com/user-attachments/assets/67f8ed96-abb8-4368-b3f3-b2a3484bd4b9" />

- [ ] Confirm the firmware version meets the minimum requirement.

  | Model                       | Version                         |
  | --------------------------- | ------------------------------- |
  | BK1600/BK1600Ultra          | V1.3.0A_R006.072_M4848_00000039 |
  | SolidFlex2000/PowerFlex2000 | V1.3.09_R00D.012_M4801_00000015 |

<img width="400" alt="4fw_version" src="https://github.com/user-attachments/assets/7fb6d58f-9c95-4945-b588-810e68481f5b" />


## Step 1: Download the indevolt integration folder

1. Click **Code** > **Download ZIP**.
2. Unzip the ZIP file to your computer.


## Step 2: Locate the HA configuration directory path

- **Home Assistant OS**: The configuration directory is located in `/config`.
- **Home Assistant Container**: You can access the configuration directory by locating the `configuration.yaml` file.

**Tip**: The directory should contain a `configuration.yaml` file.

```
config directory/
└── configuration.yaml
```

## Step 3: Create a custom integration directory

1. Enter the config directory.
2. Create the `custom_components` directory if it does not exist.

```
config directory/
├── custom_components/
└── configuration.yaml
```

**Note**: All custom integrations must be placed under `custom_components`, otherwise HA will not be able to recognize them.


## Step 4: Add the integration file

1. Create the `indevolt` directory in the config directory.
2. Copy all files from the unzipped folder (except `README.md`) into the `indevolt` directory.

Once installed correctly, your configuration directory should look like this:

```
config directory/
└── custom_components/
    └── indevolt/
        ├── __init__.py
        ├── config_flow.py
        ├── const.py
        ├── coordinator.py
        ├── entity.py
        ├── manifest.json
        ├── sensor.py
        ├── indevolt.py
        ├── strings.json
```

## Step 5: Restart Home Assistant

1. Select **Settings** > **System** in the web interface.
2. Click the restart icon in the upper right corner.
3. Click **Restart Home Assistant**.
4. Click **RESTART**.

<img width="1000" alt="5restart_ha" src="https://github.com/user-attachments/assets/1270a590-faf8-43a4-8989-27923d1f3887" />


## Step 6: Add integration to Home Assistant

1. After restarting, enter the web interface and select **Settings** > **Devices & services**.
2. Click **+ADD INTEGRATION** in the lower right corner.
3. Search for integration INDEVOLT.
4. Configuration parameters:
   - host: Device IP address, which can be obtained by checking the router/app.
   - port: Default 8080.
   - scan_interval: Used to control the frequency of data updates, default is 30 seconds.
   - device_model: the model of your Indevolt device
5. Click **SUBMIT** to finish the installation.

<img width="600" alt="6add_integration" src="https://github.com/user-attachments/assets/b435073a-cd55-49fb-bcae-ffd698821c1a" />
<img width="300" alt="7add_device" src="https://github.com/user-attachments/assets/ce18f3e0-9658-4052-bbbd-02dfea022dbb" />


## View Integration

Select the INDEVOLT integration to display the device and entity information.

<img width="800" alt="8view_integration" src="https://github.com/user-attachments/assets/731e767d-c41c-4c5e-b1f6-a6eae28fffd7" />



## Update integration

1. Download the latest version of the integration file.
2. Replace the files in `custom_components/indevolt`.
3. Restart Home Assistant.
4. To ensure all new features are loaded, remove the device from Home Assistant and then re-add it.

## FAQ

| Problem Description | Solutions |
| ------------------- | ----------|
| Integration not found in search list | Verify the integration file is located in the correct folder: `custom_components/indevolt`. |
| - Unable to add  device. <br> - Unable to connect to the device.  <br> - No data available   | This is typically caused by an **HTTP request failure**. <br>  1.  Verify the device is powered on.<br> 2. Confirm the device's IP address is correct.<br> 3. Check the device's network status in Indevolt app.<br>4. Ensure you have met all the [prerequisites](#prerequisites). |

If you encounter any issues, please check the **Home Assistant logs** for detailed error messages.

## Contribute

We welcome your feedback and contributions! Please feel free to open an issue with your suggestions or submit a pull request.
