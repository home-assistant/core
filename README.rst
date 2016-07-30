Home Assistant |Build Status| |Coverage Status| |Join the chat at https://gitter.im/home-assistant/home-assistant| |Join the dev chat at https://gitter.im/home-assistant/home-assistant/devs|
==============================================================================================================================================================================================

Home Assistant is a home automation platform running on Python 3. The
goal of Home Assistant is to be able to track and control all devices at
home and offer a platform for automating control.

To get started:

.. code:: bash

    python3 -m pip install homeassistant
    hass --open-ui

Check out `the website <https://home-assistant.io>`__ for `a
demo <https://home-assistant.io/demo/>`__, installation instructions,
tutorials and documentation.

|screenshot-states|

Examples of devices Home Assistant can interface with:

-  Monitoring connected devices to a wireless router:
   `OpenWrt <https://openwrt.org/>`__,
   `Tomato <http://www.polarcloud.com/tomato>`__,
   `Netgear <http://netgear.com>`__,
   `DD-WRT <http://www.dd-wrt.com/site/index>`__,
   `TPLink <http://www.tp-link.us/>`__,
   `ASUSWRT <http://event.asus.com/2013/nw/ASUSWRT/>`__ and any SNMP
   capable Linksys WAP/WRT
-  `Philips Hue <http://meethue.com>`__ lights,
   `WeMo <http://www.belkin.com/us/Products/home-automation/c/wemo-home-automation/>`__
   switches, `Edimax <http://www.edimax.com/>`__ switches,
   `Efergy <https://efergy.com>`__ energy monitoring, and
   `Tellstick <http://www.telldus.se/products/tellstick>`__ devices and
   sensors
-  `Google
   Chromecasts <http://www.google.com/intl/en/chrome/devices/chromecast>`__,
   `Music Player Daemon <http://www.musicpd.org/>`__, `Logitech
   Squeezebox <https://en.wikipedia.org/wiki/Squeezebox_%28network_music_player%29>`__,
   `Plex <https://plex.tv/>`__, `Kodi (XBMC) <http://kodi.tv/>`__,
   iTunes (by way of
   `itunes-api <https://github.com/maddox/itunes-api>`__), and Amazon
   Fire TV (by way of
   `python-firetv <https://github.com/happyleavesaoc/python-firetv>`__)
-  Support for
   `ISY994 <https://www.universal-devices.com/residential/isy994i-series/>`__
   (Insteon and X10 devices), `Z-Wave <http://www.z-wave.com/>`__, `Nest
   Thermostats <https://nest.com/>`__,
   `RFXtrx <http://www.rfxcom.com/>`__,
   `Arduino <https://www.arduino.cc/>`__, `Raspberry
   Pi <https://www.raspberrypi.org/>`__, and
   `Modbus <http://www.modbus.org/>`__
-  Interaction with `IFTTT <https://ifttt.com/>`__
-  Integrate data from the `Bitcoin <https://bitcoin.org>`__ network,
   meteorological data from
   `OpenWeatherMap <http://openweathermap.org/>`__ and
   `Forecast.io <https://forecast.io/>`__,
   `Transmission <http://www.transmissionbt.com/>`__, or
   `SABnzbd <http://sabnzbd.org>`__.
-  `See full list of supported
   devices <https://home-assistant.io/components/>`__

Build home automation on top of your devices:

-  Keep a precise history of every change to the state of your house
-  Turn on the lights when people get home after sunset
-  Turn on lights slowly during sunset to compensate for less light
-  Turn off all lights and devices when everybody leaves the house
-  Offers a `REST API <https://home-assistant.io/developers/rest_api/>`__
   and can interface with MQTT for easy integration with other projects
   like `OwnTracks <http://owntracks.org/>`__
-  Allow sending notifications using
   `Instapush <https://instapush.im>`__, `Notify My Android
   (NMA) <http://www.notifymyandroid.com/>`__,
   `PushBullet <https://www.pushbullet.com/>`__,
   `PushOver <https://pushover.net/>`__, `Slack <https://slack.com/>`__,
   `Telegram <https://telegram.org/>`__, `Join <http://joaoapps.com/join/>`__, and `Jabber
   (XMPP) <http://xmpp.org>`__

The system is built using a modular approach so support for other devices or actions can
be implemented easily. See also the `section on
architecture <https://home-assistant.io/developers/architecture/>`__
and the `section on creating your own
components <https://home-assistant.io/developers/creating_components/>`__.

If you run into issues while using Home Assistant or during development
of a component, check the `Home Assistant help
section <https://home-assistant.io/help/>`__ how to reach us.

.. |Build Status| image:: https://travis-ci.org/home-assistant/home-assistant.svg?branch=master
   :target: https://travis-ci.org/home-assistant/home-assistant
.. |Coverage Status| image:: https://img.shields.io/coveralls/home-assistant/home-assistant.svg
   :target: https://coveralls.io/r/home-assistant/home-assistant?branch=master
.. |Join the chat at https://gitter.im/home-assistant/home-assistant| image:: https://img.shields.io/badge/gitter-general-blue.svg
   :target: https://gitter.im/home-assistant/home-assistant?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge
.. |Join the dev chat at https://gitter.im/home-assistant/home-assistant/devs| image:: https://img.shields.io/badge/gitter-development-yellowgreen.svg
   :target: https://gitter.im/home-assistant/home-assistant/devs?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge
.. |screenshot-states| image:: https://raw.github.com/home-assistant/home-assistant/master/docs/screenshots.png
   :target: https://home-assistant.io/demo/
