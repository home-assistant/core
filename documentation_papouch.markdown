---
title: Papouch
description: Instructions on how to integrate Papouch devices into Home Assistant.
ha_category:
  - Binary Sensor
  - Button
  - Number
  - Select
  - Sensor
  - Switch
ha_release: 2026.8
ha_iot_class: Local Polling
ha_config_flow: true
ha_domain: papouch
ha_diagnostics: true
---

The **Papouch** integration allows you to integrate your [Papouch](https://papouch.com/) hardware devices into Home Assistant.

The integration works by continuously polling the device for real-time data and updating the corresponding Home Assistant entities. In addition to monitoring, it provides command entities to control the device outputs, and configuration entities to adjust hardware settings, such as counter modes and sensor types.

{% include integrations/config_flow.md %}

## Supported devices

Currently, only Ethernet devices in **WEB** mode are supported:

- **Quido ETH** (Input/output modules)
- **TH2E** (Thermometers and environmental sensors)
- **TME** (Multi-channel thermometers)
  - **TME Multi / Radio**
- **Papago** (Ethernet sensors and meteo stations)
  - **Meteo**
  - **5HDI DO**
  - **2TH**
  - **TH 2DI DO**

## Device discovery

All supported Papouch devices feature DHCP discovery. Once the integration is active in your Home Assistant instance, devices sending DHCP requests will automatically appear in the **Discovered** section on the Integrations page. Clicking **Configure** will guide you through the setup process.

{% note %}
This will be active if DHCP is enabled in the device. Note that devices with an active password configured may fail or be skipped during automatic DHCP discovery because authentication is required.
{% endnote %}

Active discovery is also triggered automatically when you manually add the integration via the user interface. It will scan your local network using UDP broadcasts and present a list of available, unregistered devices along with their names, locations, and IP addresses. However, if a device has a password set, it will not be displayed in the list of available devices during network scans.

{% note %}
If your Home Assistant instance is running in an isolated network environment (such as WSL or specific Docker network configurations) where UDP broadcasts cannot reach the container, automatic discovery will fail. In this case, you can simply select the option to enter the IP address manually during the configuration flow.
{% endnote %}

If your device was not discovered automatically, you can complete the setup manually:

1. The setup flow will always begin with an active network scan.
2. If the list of discovered devices is empty, or if you prefer not to select any of the automatically discovered devices, choose the option to enter the IP address manually.
3. Enter the device's IP address, your preferred polling interval, and the admin password (if set).
4. In the final step, you can assign the device to an area and customize its name.

{% note %}
If the device doesn't have any password set and you provide one in the setup, it will work; however, the reverse will fail if the device expects a password that is not provided.
{% endnote %}

{% note %}
Some of the devices can be run in various modes (e.g. TCP client/server, etc.). That means if you are trying to configure a device that is, for example, in TCP server mode, the integration will detect this and offer you a choice to either switch it to WEB mode or abort the configuration. Other modes are not supported since the device must operate in WEB mode for proper integration functionality.
{% endnote %}

{% note %}
The device must be powered on and reachable by Home Assistant during the initial setup. The integration cannot be configured with an offline IP address because it needs to fetch the hardware configuration data to create a valid instance.
{% endnote %}

If you need to change your selection during the manual configuration, simply close the setup dialog and start the process again.

## Reconfiguration

If your device's IP address or access password changes, you can update the integration settings without removing and re-adding the device:

1. Navigate to **Settings** > **Devices & Services**.
2. Click the three dots next to your Papouch integration and select **Reconfigure**.
3. Update the IP address and/or password as needed.

{% note %}
The reconfiguration flow updates the connection credentials and IP address used by Home Assistant to communicate with the device. It does not modify the physical device's internal configuration (such as changing its IP address or password on the device itself).
{% endnote %}

## Polling interval

After creating a configuration for a device, you can change its polling interval by:

1. Navigate to **Settings** > **Devices & Services**.
2. Click the cog icon right next to the three dots in your Papouch integration, enter a new polling interval, and click **Submit**.

## Diagnostics

This integration supports Home Assistant diagnostics, allowing you to export technical details and configuration states to help troubleshoot issues. You can download the diagnostic data by:

1. Navigating to **Settings** > **Devices & Services**.
2. Finding your Papouch integration and clicking the three dots on the configuration entry.
3. Selecting **Download diagnostics**.

## Using the device

While the device's built-in web interface remains the primary place for core configuration, this integration exposes certain settings directly within Home Assistant for your convenience.

{% important %}
If you change settings directly via the device's web interface, the integration will not automatically detect all of these changes. We highly recommend **reloading** the integration (Settings > Devices & Services > three dots > **Reload**) after making external changes to keep the states synchronized.
{% endimportant %}

### Known limitations and nuances

This section describes various limitations and nuances that can occur while using the devices.

#### Number entities

When adjusting a `number` entity using the up/down arrows in the Home Assistant UI, every single step immediately sends a command to the device. To jump to a specific value without sending intermediate commands, type the exact number directly into the input field and press Enter.

#### Select entities

Select entities (such as counter modes or sensor types) are not continuously polled. If you change them directly on the device's web interface, Home Assistant will be unaware of the change until the integration is reloaded.

{% warning %}
Changing the operating mode via a `select` entity causes the physical device to restart. For this reason, it is strongly advised **not** to use these select entities in automations.
{% endwarning %}

#### Units of measurement

Changing the physical unit of measurement on the device's web interface will not automatically update the unit in Home Assistant. Doing so may also disrupt your long-term statistics and require you to fix the historical data manually.

#### Dynamic entities

Some devices (e.g., TH2E) expose a variable number of entities depending on the configured sensor type. If you change the sensor type, some previously active entities may become unavailable. You can safely delete these orphaned entities from Home Assistant; their historical data will remain intact, and they will be recreated if you ever switch the sensor type back. To recreate entities after changing hardware configurations, use a reload action (more details in [Troubleshooting](#troubleshooting)).

### Quido

The integration provides the following entities for Quido devices:

- **Binary sensor**: Watches the state of digital inputs.
- **Button**: Allows bulk connecting/disconnecting of all outputs and resetting counters.
- **Number**:
  - Decreasing counters by a specific value (up to 2<sup>32</sup> - 1).
  - Setting the output connection/disconnection duration (from 0.5s to 127.5s with 0.5s step).
- **Select**: Changes the operation mode of the input counters.
- **Sensor**: Reads temperature and pulse counts.
- **Switch**: Changes the state of individual outputs.

The official manual can be found in the downloads section of the [Quido product page](https://papouch.com/quido-eth-4-4-4-vstupy-4-vystupy-teplomer-ethernet-p4646/?cid=145&vid=1797).

### TH2E

The integration provides the following entities for TH2E devices:

- **Button**: Triggers automatic configuration of the connected sensor type (triggers a restart).
- **Select**: Allows manual selection and configuration of the connected sensor type.
- **Sensor**: Provides environmental readings depending on the configured sensor type.

For more details, see the official manual available in the downloads section of the [TH2E product page](https://papouch.com/th2e-ethernetovy-teplomer-s-vlhkomerem-p4825/?vid=2374).

### TME / TME Multi / TME Radio

The integration provides the following entities for TME devices:

- **Sensor**: Provides environmental readings depending on the configured sensor type.

For more details, see the official manuals available in the downloads section of the [TME](https://papouch.com/tme-ethernetovy-teplomer-p4602/?sti=635677&vid=1879) and [TME Multi/Radio](https://papouch.com/tme-radio-bezdratovy-meric-teploty-a-vlhkosti-p4603/?sti=635678&vid=2965) product pages.

### Papago

Papago is a family of devices.

#### METEO

The integration provides these entities:

- **Button**: Automatic type configuration of the sensor (only for sensors A and B, since sensor C has only 1 possible sensor type. This does not cause a restart).
- **Select**: Allows manual selection and configuration of the connected sensor type.
- **Sensor**: Various sensors depending on the type of the sensor.

The official manual can be found in the downloads section of the [Papago Meteo product page](https://papouch.com/papago-meteo-eth-zakladna-prumyslove-meteostanice-s-ethernetem-a-poe-p6878/?vid=4887).

#### 5HDI DO

The integration provides the following entities:

- **Binary sensor**: Watches the state of digital inputs.
- **Button**: Allows bulk connecting/disconnecting of all outputs and resetting counters.
- **Number**:
  - Decreasing counters by a specific value (up to 2<sup>32</sup> - 1).
  - Setting the output connection/disconnection duration (from 0.5s to 127.5s with 0.5s step).
- **Select**: Changes the operation mode of the input counters.
- **Sensor**: Reads temperature and pulse counts.
- **Switch**: Changes the state of individual outputs.

The official manual can be found in the downloads section of the [Papago 5HDI DO product page](https://papouch.com/papago-5hdi-do-eth-5-digitalni-vstup-a-1-rele-p3132/).

#### 2TH

The integration provides these entities:

- **Button**: Automatic type configuration of both sensors (does not cause a restart).
- **Sensor**: Various sensors depending on the type of the sensor.
- **Select**: Allows manual selection and configuration of the connected sensor type.

The official manual can be found in the downloads section of the [Papago 2TH product page](https://papouch.com/papago-2th-eth-2-mereni-teploty-vlhkosti-a-rosneho-bodu-s-ethernetem-p2989/).

#### TH 2DI DO

- **Binary sensor**: Watches the state of digital inputs.
- **Button**:
  - Allows bulk connecting/disconnecting of all outputs and resetting counters.
  - Automatic type configuration of both sensors (does not require a restart).
- **Number**:
  - Decreasing counters by a specific value (up to 2<sup>32</sup> - 1).
  - Setting the output connection/disconnection duration (from 0.5s to 127.5s with 0.5s step).
- **Select**:
  - Changes the operation mode of the input counters.
  - Allows manual selection and configuration of the connected sensor type.
- **Sensor**:
  - Reads temperature and pulse counts.
  - Various sensors depending on the type of the sensor.
- **Switch**: Changes the state of individual outputs.

The official manual can be found in the downloads section of the [Papago TH 2DI DO product page](https://papouch.com/papago-th-2di-do-eth-environment-monitor-p3159/).

## Troubleshooting

The integration detects supported sensors and outputs during its initial setup. If you change the physical configuration of your Papouch device (for example, plugging a new sensor into an empty port, or switching a port's operating mode between a thermometer and a hygrometer), the new entities will not appear automatically, and the old ones will not be removed.

To apply these hardware changes:

1. Make sure your device has fully restarted and is working with the new configuration.
2. Navigate to **Settings** > **Devices & Services**.
3. Click the three dots next to your Papouch integration and select **Reload**.

The integration will fetch the updated hardware layout and create the new entities. The old entity (e.g., the previous thermometer) will become `unavailable` and you can manually delete it from the Home Assistant entity registry. Thanks to MAC address identification, you will not lose any historical data for the sensors that remained untouched.

{% include integrations/remove_device.md %}
