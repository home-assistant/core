"""Support for I2C MCP23017 chip."""

DOMAIN = "mcp23017"

import threading

""" Lockable device dictionnary/list enabling thread-safe usage of multiple:
    - components within one device (unique device initialization)
    - devices within a system
"""
class deviceList:
   def __init__(self):
      self._lock = threading.Lock()
      self._instances = {}

   def __enter__(self):
      self._lock.acquire()
      return self

   def __exit__(self, type, value, traceback):
      self._lock.release()

   def __contains__(self, key):
       return key in self._instances

   def __getitem__(self, key):
      if key not in self._instances:
         return None
      return self._instances[key]

   def __setitem__(self, key, value):
      self._instances[key] = value

devices = deviceList()

