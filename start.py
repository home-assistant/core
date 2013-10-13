#!/usr/bin/python2
""" Starts home assistant with all possible functionality. """

import homeassistant.bootstrap

homeassistant.bootstrap.from_config_file("home-assistant.conf")
