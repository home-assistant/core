# We have come to the point where I need help from you.

As said before, we are in good contact with SmartThings and we're making awesome progress.
The change that is happening also requires a refactor of the library.
Since I want to be 100% confident that we don't break existing users, I need more up to date test data.
This test data can help me to see how all devices are rendered (like I said before, I only have Philips hue lights coupled to SmartThings).

So I have made a way to get the data that I need in a fairly simple way, but I want to keep the risk as low as possible.

## How you can help?

So to keep the risk low, I suggest only to participate if you meet one of the following criteria:
1. You don't have the integration running (because you only have 24h tokens for example)
2. Or you have a test environment where you can do whatever you like
3. Or you don't rely on the SmartThings integration for your daily life
4. Or you know what you are doing

You will need to install the integration again, but this installation is not backwards compatible with the current version of the integration.
There are also custom components for SmartThings, please also make sure you don't have these installed (if you have, please remove them).

> [!WARNING]  
> Please, if you are not confident in completing this, don't feel forced to do so (as in, don't think your devices will not be supported if you don't do this).


## So now what?

So my current priority is making sure that the current integration works on-par with after the refactor.
With the data I hope to get from you, I can also look into how certain devices does certain things, so it will indirectly also help for future features, but again, not main priority right now.

So I have rebuilt the integration with a new architecture, suited for what will come in the future.
So in a quick summary of what will come, this little guide will help you install that integration as custom component.

> [!WARNING]  
> If you want to find out your current access token, please use the [script](https://github.com/home-assistant/core/issues/133623#issuecomment-2593694731 I wrote before. Keep in mind that this only works for backups pre-2025.1 or if you have encryption disabled in 2025.2 (untested)

1. Acquire a personal access token from SmartThings (you can follow the current documentation for that).
2. Install the SmartThings integration like usual

> [!WARNING]  
> Make sure you don't have a custom component for SmartThings installed, if you have, please remove it.

3. Please take screenshots of every device page in Home Assistant for SmartThings, with all entities visible. (If you have similar devices E.g. 2 SmartTags, and they share the same entities, you only need to take one screenshot).
4. Store these screenshots somewhere on your disk, as I will need them :)
5. Remove the integration. 

> [!WARNING]  
> This is important to do, as the core integration has code that runs when you delete it, which is required to make sure you system keeps sane.

6. Install the PR as a custom component:
```shell
cd /config
curl -o- -L https://gist.githubusercontent.com/bdraco/43f8043cb04b9838383fd71353e99b18/raw/core_integration_pr | bash /dev/stdin -d smartthings -p 137940
```
You can find the PR you are installing [here](https://github.com/home-assistant/core/pull/137940). The PR will use the updated library, located [here](https://github.com/pySmartThings/pysmartthings/pull/131).
This will install the PR as custom component in `/config/custom_components/smartthings`.

7. Restart Home Assistant
8. Install the integration. You will notice the config flow is different.
9. To download the data, go to the integration entries page, press the 3 dots on the SmartThings integration and press "Download diagnostics". This JSON file contains an overview of all the devices you have in your location, and it contains the status of every device.
10. Additionally, if you now see devices and entities for the SmartThings integration: Great! That means that the library is already able to understand the devices that you have. If this is the case, also please add screenshots of the device pages like before, so it can be compared to the previous screenshots.

> [!WARNING]  
> Previously, the core integration created complimentary useless power and energy sensors for every switch capability, independent of if the device reported power or energy. So if you notice a few less entities, that is why.

11. Remove the integration entry again, and remove the custom component by running `rm -rf /config/custom_components/smartthings`
12. Please send me the JSON file and the screenshots to joost.lekkerkerker@nabucasa.com.

> [!WARNING]  
> The custom integration isn't better than the core one at this point, so please don't keep running it. It's only for testing purposes at this point.

## How this data will be used

The JSON you send can be used as test data in the repository, to make sure there are no regressions in the future.
This means that they will be published in a public repository.
The screenshots will be used to compare the current state of the integration with the new state of the integration.

Keep in mind that generally the JSON file does not contain any personal data.

### Redacting personal data

So there are a few places that _could_ be user identifiable, be sure to check the JSON file for things like `geolocation`.
Other things that are user identifiable are the locationId, deviceId and roomId.
They are not usable to link to you, and since nobody except for me knows they are from you, the risk is very low.

If you do happen to want to redact data in the file, that's no problem, but to make sure the file is still usable, please follow these quick guidelines:
- Please make sure the structure and content is the same (Don't replace `123` with `"abc"` for example)
- If you change UUIDs (Those long strings with 4 dashes), make sure you change all occurrences of that UUID to the same redacted value (so, `abc` -> `def` & `abc` -> `def` instead of `abc` -> def & `abc` -> `xyz`).

## Conclusion

Again, I am quite hyped on what will come, so much that my mom actually sent me a message to ask how I was doing since I didn't give a sign of life for a few days lol.

And like said before, I don't have all the room and time of the world to individually help every one of you with this, so if you don't feel confident in doing this, please don't feel forced to do so.


Oh! I almost forgot my wishlist of devices that I still need:
- ACs
- Media players
- Garage doors
- Locks
- Fans
- More sensors
- Zwave?

And some questions that I had while examining the code:
- Devices with `energySaved` entity >0
- Devices with `powerEnergy` entity >0
- Are there devices with higher power than 0?

(so if you happen to have answers to one of those, your fixtures are also welcome!)