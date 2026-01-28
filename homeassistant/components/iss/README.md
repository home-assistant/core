# ISS (International Space Station) Home Assistant Integration

## How It Works
In previous versions of the integration position data was frequently
fetched from [OpenNotify](http://open-notify.org/). As it turns out
making remote API calls from the integration that frequently are
not necessary.

Instead of polling the API for coordinates we can instead periodically
fetch [TLE Data](https://en.wikipedia.org/wiki/Two-line_element_set)
and calculating the position data. Using TLE data, which can be
fetched much less frequently, and using the `skyfield` project we can
calculate position data locally. This allows us to update position
data very frequently without putting load on external APIs

TLE data is cached locally in the `Store` providing resiliency against
network failures. In addition to caching the data, the integration will
fetch this data using multiple sources. Should all sources fail, the local
cache remains available.

## Sensors
### Position
The integration will expose an ISS Position sensor, allowing the station's
position to be displayed on the map, and used in automations.

Coordinates are calculated using publicly available TLE data from multiple
sites.

### People
The integration will expose a sensor which tracks how many people
are onboard the station. This data is sourced from
http://open-notify.org/Open-Notify-API/People-In-Space/