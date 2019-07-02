# Fortigate Presence Sensor

This is a Fortigate presence sensor based on device detection of the Fortigate API

### Installation

Copy this folder to `<config_dir>/custom_components/fortigate/`.

Add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
fortigate:
  host: <host_IP>
  username: homeassistant
  password: <api_key>
  devices: 
    - dev1
    - dev2
```
The dev1 and dev2 are devices detected by the fortigate (hostname)


Configure the Fortigate with the homeassistant api user and assign its minimum rights profile :
```
config system accprofile
    edit "homeassistant_profile"
        set authgrp read
    next
end

config system api-user
    edit "homeassistant"
        set api-key <api key>
        set accprofile "homeassistant_profile"
        set vdom "root"
        config trusthost
            edit 1
                set ipv4-trusthost <trusted subnets>
            next
        end
    next
end
```

If the rights of the profile are not sufficient, you will get the error :

ERROR (MainThread) [homeassistant.core] Error doing job: Task exception was never retrieved
And as well a python exception 'pyFGT.fortigate.FGTValueError'
