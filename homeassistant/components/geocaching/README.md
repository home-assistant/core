# Geocaching Integration
## Overview
The Geocaching integration allows you to see some information related to your Geocaching profile, as well as to track both Trackables and Geocaches. For each Trackable and Geocache, a device with related entities is generated allowing you to extract the data. For example, you are able to display both Trackables and Geocaches on a map using the location entity.

The integration uses the [geocachingapi-python](https://github.com/Sholofly/geocachingapi-python) library, which in turn authenticates you using OAuth2 in order to send API requests to the [Geocaching API](https://api.groundspeak.com/documentation).

## Features
### Account information
After the integration has been configured, a device for your Geocaching account is generated, including entities to show statistics such as the total number of finds, hides and souvenirs.

### Tracked Geocaches
You have the option of configuring a number of tracked Geocaches. For each geocache, several entities are generated allowing you to see data about the cache, such as the number of favourite points, if you have found it, when it was hidden and its location.

### Tracked Trackables
You have the option of configuring a number of tracked Trackables. For each Trackable, several entities are generated allowing you to see data about the trackable, such as which cache it currently resides in, how far it has travelled and its location.

### Nearby Geocaches
You have the option of enabling the nearby Geocaches feature, which will generate a device for each cache that is near to your home location set in Home Assistant. Currently, there is a limitation for this feature as the devices will not be dynamically added. Instead, they are only set up during the configuration. Therefore, new nearby caches will not be picked up unless the integration is reconfigured.

## Configuration
After adding the integration, you will be guided through the configuration process. The first step is authenticating your Geocaching account using OAuth2, in order to make API calls to the Geocaching API to gather all the necessary data. Then, you can optionally select Geocaches and Trackables to track, and set up the nearby caches feature if you would like.

## Displaying the information
As mentioned, the integration provides several entities that you can use to extract information from the Geocaching service. For your convenience, we provide a few preconfigured cards that you could use to display the information. Note, however, that you have to configure them as you will probably have different caches and trackables. For example, setting the reference code to one of the caches you are tracking in the tracked Geocache card.

### A tracked Trackable
```yml
type: vertical-stack
title: Trackable TB89YPV
cards:
  - type: entities
    entities:
      - entity: sensor.geotrackable_tb89ypv_name
        name: Name
        icon: mdi:alpha-n
        secondary_info: none
      - entity: sensor.geotrackable_tb89ypv_owner
        name: Owner
        icon: mdi:account
        secondary_info: none
      - entity: sensor.geotrackable_tb89ypv_release_date
        name: Release date
        icon: mdi:calendar-arrow-right
        secondary_info: none
      - entity: sensor.geotrackable_tb89ypv_traveled_distance
        name: Distance travelled
        icon: mdi:map-marker-distance
        secondary_info: last-changed
      - entity: sensor.geotrackable_tb89ypv_current_cache_name
        name: Current cache location
        icon: mdi:treasure-chest
        secondary_info: last-changed
      - entity: sensor.geotrackable_tb89ypv_current_cache_code
        name: Current cache ID
        icon: mdi:id-card
        secondary_info: last-changed
  - type: markdown
    content: >-
      {% set trackable_code = 'TB89YPV' %}
      {% set logs_to_display = 5 %}

      {% set sensor_id = 'sensor.geotrackable_' + trackable_code | lower +
      '_location' %}

      |Date|User|Location|Distance|

      |---|---|---|---|

      {% for log in state_attr(sensor_id, 'travel_log')[-logs_to_display:] |
      reverse -%}

      |{{log.date}}|{{log.username}}|{{log.location_name}}|{{log.distance_travelled}}|

      {% endfor %}
    title: Travel log
```

### A tracked Geocache
```yml
type: entities
title: Geocache GC9P6FN
entities:
  - entity: sensor.geocache_tracked_gc9p6fn_name
    name: Name
    icon: mdi:alpha-n
    secondary_info: none
  - entity: sensor.geocache_tracked_gc9p6fn_owner
    name: Owner
    secondary_info: none
  - entity: sensor.geocache_tracked_gc9p6fn_location
    name: Location
    secondary_info: last-updated
  - entity: sensor.geocache_tracked_gc9p6fn_hidden_date
    icon: ""
    name: Hide date
    secondary_info: none
  - entity: sensor.geocache_tracked_gc9p6fn_favorite_points
    name: Favorite points
    secondary_info: last-updated
  - entity: sensor.geocache_tracked_gc9p6fn_found
    name: Found
    secondary_info: none
  - entity: sensor.geocache_tracked_gc9p6fn_found_date
    name: Found date
    secondary_info: none
```

### Nearby Geocaches
```yml
type: map
title: Nearby caches
entities:
  - entity: sensor.geocache_nearby_gc9p6fn_location
    label_mode: state
  - entity: sensor.geocache_nearby_gc1dqpm_location
    label_mode: state
theme_mode: auto
```