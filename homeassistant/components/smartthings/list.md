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
- Are there devices with higher power than 0? Yes, I saw one pass by

# Things to fix:

- ~~Remove complimentary useless power and energy sensor for every switch capability~~ Removed them, took more code to maintain and they were useless in the first place
- Try to see if the microwave door stops being a cover 
- Device info
- Don't show disabled capabilities
- Don't create a coordinator for the bridge?
- Locks can unlatch = open

# Things to find out

- Can we find out which device connected to which bridge?

# Things to question

- Is the list of supported (oven/dishwasher/whatever) modes finite?
- The oven setpoint, does that align with the unit of measurement of the temperature reading?
- Can disabilities be disabled dynamically?
- Is the category in the device the one set by the user?
- What are components and when do I know when to use which one? `da_ac_rac_000001` has 2 where the first hasn't been updated in 4 years. -> The disabled component capability