**Grid Connect Integration Overview**

The Grid Connect integration enables users to add and configure Grid Connect devices seamlessly via their home assistant app. It leverages the user’s smartphone Bluetooth (if available) to discover nearby devices broadcasting a pairing signal. Once a Bluetooth beacon is detected, the app initiates a secure Wi-Fi handshake, allowing the device to join the local network and be managed within the home assistant ecosystem. All user interactions occur within a clear, guided setup flow to ensure a smooth experience.

---

**Setup Process**

1. **Launch “Add Device”**
   The user taps **Add Device** in the app’s main menu to begin the process.

2. **Background Scan for Devices**

   - Immediately upon entry, the app begins scanning for Grid Connect devices via Bluetooth Low Energy (BLE).
   - Scanning runs asynchronously in the background for a configurable timeout (for example, 30 seconds).
   - Detected devices are listed dynamically as they appear.

3. **Automatic Discovery**

   - If one or more devices are found, they populate a selectable list with device IDs or model names.
   - The user selects their device from the list to proceed.

4. **Manual Specification (Fallback)**

   - If no devices are detected within the scan period, the user is prompted to **Specify Device Manually**.
   - Upon selecting manual addition, the app presents a list of supported Grid Connect models for the user to choose from.

5. **Device Reset and Pairing Guidance**

   - For manual additions, the app displays step-by-step instructions on how to factory-reset the device to its default Bluetooth pairing mode.
   - Once reset, the user confirms in the app that the device is ready to pair, and background scanning resumes.

6. **Wi-Fi Configuration**

   - After Bluetooth pairing, the app prompts the user to select their home Wi-Fi network and enter credentials (or confirm previously saved credentials).
   - The app securely transmits this information to the device over the established Bluetooth link, which then connects itself to the Wi-Fi network.

7. **Final Details: Name and Location**
   - Once the device is online, the app displays a success screen.
   - The user assigns a friendly name (for example, “Living Room Sensor”) and selects a room or zone within their home assistant layout.
   - The device is now fully integrated and appears on the dashboard for control and monitoring.

---

**Development To-Do**

```yaml
1. Implement Bluetooth Discovery:
  - Integrate a suitable BLE library (e.g., Bleak) into config_flow.py.
  - Create functions to scan for devices advertising the Grid Connect service UUID.

2. Add Background Scanning:
  - Design an asynchronous task in the config flow that continuously scans for a specified duration.
  - Update the UI dynamically as devices are found without blocking the main thread.

3. Support Manual Device Specification:
  - Extend the flow to include a “Specify Device Manually” option when no devices appear automatically.
  - Maintain a JSON-backed registry of supported Grid Connect models for selection.

4. Provide Reset & Pairing Instructions:
  - Develop UI panels with clear, illustrated steps on how to reset each device type.
  - Link the “Confirm Reset” action to re-trigger Bluetooth scanning.

5. Manage Wi-Fi Credential Exchange:
  - Securely transmit Wi-Fi SSID and password over the BLE characteristic.
  - Handle errors such as authentication failures or timeouts, with appropriate user feedback.

6. Enable Naming and Room Assignment:
  - After successful network join, prompt for a user-friendly device name.
  - Integrate with Home Assistant’s area registry to allow room selection or creation.

7. Error Handling and Edge Cases:
  - Cover scenarios such as Bluetooth permissions denied, network unreachable, or device already claimed.
  - Ensure the flow can gracefully abort and offer retries or alternate options.
```
