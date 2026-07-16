# Programmer documentation

This documentation is divided into two parts where first one is for describing the structure of the integration and second one is for adding a new device into the integration.

# Big picture

TODO

# Adding a new device

TODO

        each device (e.g. Quido) should have various methods and these methods should return structure that tells the UI how to create them, this is done for preventing collisions between hardware layer and software one

        Parameters of the buttons:
        First and second parameter should be the same (coordinator and entry)
        third - name visible in HA
        forth - function that will be looked up in THIS class
        fifth - suffix for item id, should be unique and describes the button
