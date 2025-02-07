
---

# GRYF_SMART Integration for Home Assistant

This document describes how to configure and use the GRYFSMART integration with Home Assistant. The integration supports both YAML configuration and Config Flow (UI-based setup).

---

## 1. Important Integration Information

### 1.1 How to Use the ID

The ID is a combination of the driver ID and the cell number (for outputs, inputs, etc.).  
```
 XY
 - X is the driver ID
 - Y is the cell number
```

### 1.2 Communication

To connect GRYFSMART, you can use either a Physical RS-232 connection or a USB/RS-232 converter. You need to know the address of the device. Typically, it is "/dev/ttyS0" for a physical RS-232 port, or "/dev/ttyUSB0" for a converter. You can list all devices using the following commands:

##### If you are using a converter:
```bash
ls /dev/ttyUSB*  # if you are using a converter
```

##### If you are using a physical port:
```bash
ls /dev/ttyS*    # if you are using a physical port
```

### 1.3 Module Count

The module count is the number of modules in the network.

### 1.4 Entities

**Gryf SMART driver supports 5 types of functions:**

- **Relay Output (O)**
- **Input (I)**
- **PWM**
- **Temperature Input (T)**
- **Cover Output**

#### 1.4.1 Light

- **Type of function:** Relay Output
- **Services:** turn_on, turn_off
- **Icon:** lightbulb
- **Entity type:** light
- **Configuration scheme:** classic
- **Device class:** None

#### 1.4.2 Switch

- **Type of function:** Relay Output
- **Services:** turn_on, turn_off, toggle
- **Icon:** switch, outlet
- **Entity type:** switch
- **Configuration scheme:** device class
- **Device class:** switch, outlet
- **Default device class:** switch

#### 1.4.3 Thermostat

- **Type of function:** Relay Output and Temperature Input
- **Services:** turn_on, turn_off, toggle, set_temperature
- **Entity type:** climate
- **Configuration scheme:** thermostat 
  ```yaml
  thermostat:
      - name:  # Name of the entity
        t_id:  # Thermometer ID
        o_id:  # Output ID
  ```
  In Config Flow, you enter the t_id into the "extra" parameter and the o_id into the "id" parameter.
- **Device class:** None

#### 1.4.4 Binary Input

- **Type of function:** Input
- **Services:** None
- **Icon:** Specific for the chosen device class
- **Entity type:** binary_sensor
- **Configuration scheme:** device class
- **Device class:** door, garage_door, heat, light, motion, window, smoke, sound, power
- **Default device class:** opening

#### 1.4.5 PWM

- **Type of function:** PWM
- **Services:** turn_on, turn_off, toggle, set_value
- **Icon:** lightbulb
- **Entity type:** light
- **Configuration scheme:** classic
- **Device class:** None

#### 1.4.6 Thermometer

- **Type of function:** Temperature Input
- **Services:** None
- **Icon:** thermometer
- **Entity type:** sensor
- **Configuration scheme:** classic
- **Device class:** None

#### 1.4.7 Input

- **Type of function:** Input
- **Services:** None
- **Icon:** switch
- **Entity type:** sensor
- **Configuration scheme:** classic
- **Device class:** None
- **Extra information:**  
  If the input is a short press and release, the sensor state is 2; if it is a long press, the state is 3.

---

## 2. Configuring via YAML

### Example Configuration Tree
```yaml
gryfsmart:
    port: "/dev/ttyS0"          # RS-232 port location
    module_count: 10            # Number of modules in the network
    states_update: True         # Enable asynchronous state updates
    lights:                     # Lights (relay output) elements
        - name: "Living Room Lamp"
          id: 11              # Combined ID: controller 1, pin 1
        - name: "Kitchen Lamp"
          id: 28              # Combined ID: controller 2, pin 8
    buttons:                    # Buttons (inputs)
        - name: "Living Room Panel"
          id: 17              # Combined ID: controller 1, pin 7
    climate:                    # Regulator (climate) elements
        - name: "Regulator"
          o_id: 34            # Combined ID: controller 3, pin 4 (for example)
          t_id: 21            # Combined ID: controller 2, pin 1 (for example)
    binary_input:
        - name: "binary"
          id: 34
          device_class: door
```

### 2.1 Configuration Schemes

The configuration for each type follows specific rules. Remember:
- Names may include uppercase letters, numbers, and spaces, but no special characters other than “_”.
- Parameters are provided without any brackets.
- **Syntax and spacing are critical.**
- The entire configuration is stored under the key `gryfsmart:` in your `configuration.yaml`.
- The key `gryfsmart:` should appear only once.

#### Classic Scheme
```yaml
gryf_smart:
    lights:
        - name: "Example Lamp"    # Example name
          id: 11                  # Combined ID: where 1 = controller ID and 1 = pin
```

#### Device Class Scheme
```yaml
gryf_smart:
    p_cover:
        - name: "Example Blind"    # Example name
          id: 12                  # Combined ID: 1 for controller, 2 for pin
          device_class: door      # Optional device class
```

---

## 3. Configuration via Config Flow

The "extra" parameter corresponds to the device_class if it exists. In the case of a thermostat, the "extra" parameter maps to **t_id** instead. Otherwise, this parameter is not required. Additionally, the integration supports editing of individual devices and configuration. Please note that after making changes, you must reload the integration for the changes to take effect.

---

## 4. Helper Entities

Additionally, the configuration automatically generates two entities—**gryf_in** and **gryf_out**. The **gryf_in** entity receives incoming messages, and the **gryf_out** entity handles outgoing messages. However, if you are not an experienced GRYF SMART installer, you may ignore these details.

---
