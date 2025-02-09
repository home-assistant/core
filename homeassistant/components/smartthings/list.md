# device fixtures to find

- ACs
- Media players
- Garage doors
- Locks
- Fans
- More sensors
- Zwave?

- Devices with `energySaved` entity >0
- Devices with `powerEnergy` entity >0
- Are there devices with higher power than 0?

# Things to fix:

- ~~Remove complimentary useless power and energy sensor for every switch capability~~ Removed them, took more code to maintain and they were useless in the first place
- Try to see if the microwave door stops being a cover 
- Device info
- Don't show disabled capabilities

# Things to question

- Is the list of supported (oven/dishwasher/whatever) modes finite?
- The oven setpoint, does that align with the unit of measurement of the temperature reading?
- Can disabilities be disabled dynamically?
- Is the category in the device the one set by the user?