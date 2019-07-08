---
layout: page
title: "Lightwave Energy Components"
description: "Instructions on how to configure the lightwave energy component"
date: 2019-06-01 22:00
sidebar: true
comments: false
sharing: true
footer: true
logo: 
ha_category:
  - Sensor
ha_release: "0.92"
ha_iot_class: Local Polling
redirect_from:
---

[Lightwave Energy](http://https://lightwaverf.com/products/jsjslw600-lightwaverf-electricity-monitor-and-energy-monitor) integration for the Lightwave RF Energy Monitor. This component creates two sensors, one showing the current electricity usage and the other the cumulative usage for that day

There is currently support for the following device types within Home Assistant:

- Sensor

For this component to work you will need to make sure port 9761 (UDP) is open on your machines firewall

```yaml
# Example configuration.yaml entry

sensor lightwave_energy:
  - platform: lightwave_energy
    scan_interval: 30

```


{% configuration %}
  scan_interval:
    description: The update interval in seconds
    required: false
    type: integer
    default: 60
{% endconfiguration %}
