[![](https://img.shields.io/github/release/rospogrigio/localtuya-homeassistant/all.svg?style=for-the-badge)](https://github.com/rospogrigio/localtuya-homeassistant/releases)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
[![](https://img.shields.io/badge/MAINTAINER-%40rospogrigio-green?style=for-the-badge)](https://github.com/rospogrigio)

![logo](https://github.com/rospogrigio/localtuya-homeassistant/blob/master/img/logo-small.png)

A Home Assistant custom Integration for local handling of Tuya-based devices.
Device status is updated receiving push updates from the device instead of polling, so status updates are extremely fast (even if manually operated).

The following Tuya device types are currently supported:
* 1 and multiple gang switches
* Wi-Fi smart plugs (including those with additional USB plugs)
* Lights
* Covers
* Fans
* Climates (soon)

Energy monitoring (voltage, current, watts, etc.) is supported for compatible devices. 

This repository's development has substantially started by utilizing and merging code from NameLessJedi, mileperhour and TradeFace, and then was deeply refactored to provide proper integration with Home Assistant environment, adding config flow and other features. Refer to the "Thanks to" section below.

# Installation:

Copy the localtuya folder and all of its contents into your Home Assistant's custom_components folder. This is often located inside of your /config folder. If you are running Hass.io, use SAMBA to copy the folder over. If you are running Home Assistant Supervised, the custom_components folder might be located at /usr/share/hassio/homeassistant. It is possible that your custom_components folder does not exist. If that is the case, create the folder in the proper location, and then copy the localtuya folder and all of its contents inside the newly created custom_components folder.

Alternatively, you can install localtuya through HACS by adding this repository.


# Usage:

**NOTE: You must have your Tuya device's Key and ID in order to use localtuya. There are several ways to obtain the localKey depending on your environment and the devices you own. A good place to start getting info is https://github.com/codetheweb/tuyapi/blob/master/docs/SETUP.md .**

Devices can be configured in two ways:

# 1. YAML config files

Add the proper entry to your configuration.yaml file. Several example configurations for different device types are provided below. Make sure to save when you are finished editing configuration.yaml.

```
localtuya:
  - host: 192.168.1.x
    device_id: xxxxx
    local_key: xxxxx
    friendly_name: Tuya Device
    protocol_version: "3.3"
    entities:
      - platform: binary_sensor
        friendly_name: Plug Status
        id: 1
        device_class: power
        state_on: "true" # Optional
        state_off: "false" # Optional

      - platform: cover
        friendly_name: Device Cover
        id: 2
        open_close_cmds: ["on_off","open_close"] # Optional, default: "on_off"
        positioning_mode: ["none","position","timed"] # Optional, default: "none"
        currpos_dps: 3 # Optional, required only for "position" mode
        setpos_dps: 4  # Optional, required only for "position" mode
        span_time: 25  # Full movement time: Optional, required only for "timed" mode
        
      - platform: fan
        friendly_name: Device Fan
        id: 3

      - platform: light
        friendly_name: Device Light
        id: 4

      - platform: sensor
        friendly_name: Plug Voltage
        id: 20
        scaling: 0.1 # Optional
        device_class: voltage # Optional
        unit_of_measurement: "V" # Optional

      - platform: switch
        friendly_name: Plug
        id: 1
        current: 18 # Optional
        current_consumption: 19 # Optional
        voltage: 20 # Optional
```
   
Note that a single device can contain several different entities. Some examples:
- a cover device might have 1 (or many) cover entities, plus a switch to control backlight
- a multi-gang switch will contain several switch entities, one for each gang controlled

Restart Home Assistant when finished editing.

# 2. Using config flow

Start by going to Configuration - Integration and pressing the "+" button to create a new Integration, then select LocalTuya in the drop-down menu.
Wait for 6 seconds for the scanning of the devices in your LAN. Then, a drop-down menu will appear containing the list of detectes devices: you can 
select one of these, or manually input all the parameters.

![discovery](https://github.com/rospogrigio/localtuya-homeassistant/blob/master/img/1-discovery.png)

If you have selected one entry, you just have to input the Friendly Name of the Device, and the localKey. 
Once you press "Submit", the connection will be tested to check that everything works, in order to proceed.

![device](https://github.com/rospogrigio/localtuya-homeassistant/blob/master/img/2-device.png)

Then, it's time to add the entities: this step will take place several times. Select the entity type from the drop-down menu to set it up.
After you have defined all the needed entities leave the "Do not add more entities" checkbox checked: this will complete the procedure.

![entity_type](https://github.com/rospogrigio/localtuya-homeassistant/blob/master/img/3-entity_type.png)

For each entity, the associated DP has to be selected. All the options requiring to select a DP will provide a drop-down menu showing 
all the avaliable DPs found on the device (with their current status!!) for an easy identification. Each entity type has different options 
to be configured, here is an example for the "switch" entity:

![entity](https://github.com/rospogrigio/localtuya-homeassistant/blob/master/img/4-entity.png)

After all the entities have been configured, the procedure is complete, and the Device can be associated to the Area desired.

![success](https://github.com/rospogrigio/localtuya-homeassistant/blob/master/img/5-success.png)


# Energy monitoring values

Energy monitoring (voltage, current...) values can be obtained in two different ways:
1) creating individual sensors, each one with the desired name. Note: Voltage and Consumption usually include the first decimal, so 0.1 as "scaling" parameter shall be used in order to get the correct values.
2) accessing the voltage/current/current_consumption attributes of a switch, and then defining template sensors like this (please note that in this case the values are already divided by 10 for Voltage and Consumption):

```   
       sensor:
         - platform: template
           sensors:
             tuya-sw01_voltage:
               value_template: >-
                 {{ states.switch.sw01.attributes.voltage }}
               unit_of_measurement: 'V' 
             tuya-sw01_current:
               value_template: >-     
                 {{ states.switch.sw01.attributes.current }}
               unit_of_measurement: 'mA'      
             tuya-sw01_current_consumption:
               value_template: >-
                 {{ states.switch.sw01.attributes.current_consumption }}
               unit_of_measurement: 'W' 
```   

# Notes:

* Do not declare anything as "tuya", such as by initiating a "switch.tuya". Using "tuya" launches Home Assistant's built-in, cloud-based Tuya integration in lieu of localtuya.

# To-do list:

* Create a (good and precise) sensor (counter) for Energy (kWh) -not just Power, but based on it-. 
      Ideas: Use: https://www.home-assistant.io/components/integration/ and https://www.home-assistant.io/components/utility_meter/
   
* Everything listed in https://github.com/rospogrigio/localtuya-homeassistant/issues/15

# Thanks to:

NameLessJedi https://github.com/NameLessJedi/localtuya-homeassistant and mileperhour https://github.com/mileperhour/localtuya-homeassistant being the major sources of inspiration, and whose code for switches is substantially unchanged.

TradeFace, for being the only one to provide the correct code for communication with the cover (in particular, the 0x0d command for the status instead of the 0x0a, and related needs such as double reply to be received): https://github.com/TradeFace/tuya/

sean6541, for the working (standard) Python Handler for Tuya devices.

postlund, for the ideas, for coding 95% of the refactoring and boosting the quality of this repo to levels hard to imagine (by me, at least) and teaching me A LOT of how things work in Home Assistant.
