
Skip to content

    home-assistant
    core

Repository navigation

    Code
    Issues2.9k (2.9k)
    Pull requests632 (632)
    Agents
    Actions
    Projects
    Security13 (13)
    Insights

ibeacon keeps adding New Devices even if it's configured not to do so #88111
Open
Bug
Open
ibeacon keeps adding New Devices even if it's configured not to do so
#88111
Bug
@arigit
Description
arigit
opened on Feb 14, 2023 · edited by arigit
Contributor
The problem

This integration provides in its System Options a configuration flag called "Enable Newly added entities" (described as: "if newly discovered devices for ibeacon tracker should be automatically added").

I have set this to No (after having added my 3 ibeacons).

Even so, every day, I find 2 or 3 new ibeacons that get added automatically and are not mine (I don't have iphones or any apple device at home).

I use remote "BLE proxies", ESPHome devices one of which is in my garage and and I know it is able to pick up BLE transmissions from people passing by or neighbors, that is why I need to prevent iBeacon to add any new device or entity. However, ibeacon seems to ignore the flag and is adding devices and entities to my install regardless.
After 3-4 months of use, it added a few hundred "ghost devices" each with 5 entities, and these can only be removed manually from the registry files (the GUI is not able to delete them), so this is highly annoying.
What version of Home Assistant Core has the issue?

2023.2.4
What was the last working version of Home Assistant Core?

None
What type of installation are you running?

Home Assistant Container
Integration causing the issue

ibeacon
Link to integration documentation on our website

https://www.home-assistant.io/integrations/ibeacon/
Diagnostics information

Nothing specific to share here.
There is no way to stop ibeacon to keep discovering and adding beacons and entities
Example YAML snippet

No response
Anything in the logs that might be useful for us?

No response
Additional information

No response
Activity
Next
home-assistant
added
integration: ibeacon
on Feb 14, 2023
home-assistant
assigned
bdraco
on Feb 14, 2023
home-assistant
home-assistant commented on Feb 14, 2023
home-assistant
bot
on Feb 14, 2023

Hey there @bdraco, mind taking a look at this issue as it has been labeled with an integration (ibeacon) you are listed as a code owner for? Thanks!
Code owner commands

(message by CodeOwnersMention)

ibeacon documentation
ibeacon source
(message by IssueLinks)
arigit
arigit commented on Feb 14, 2023
arigit
on Feb 14, 2023
ContributorAuthor

There are multiple ppl complaining about this issue, it's been going on for a while, not sure why it wasn't reported here, https://community.home-assistant.io/t/ibeacon-integration-keeps-adding-devices-even-if-it-is-configured-not-to-add-new-devices/534736/3
arigit
mentioned this on Feb 15, 2023

    ESPHome bluetooth proxy has no way to disable discovery #88129

bkvargyas
bkvargyas commented on Apr 8, 2023
bkvargyas
on Apr 8, 2023

I've been seeing this issue for a while as well, I get about 5-6 entries a day from a single device. I've disabled adding new entries, but it still persists. Using ESPHome Bluetooth Proxy on a Olimux PoE device. Latest ESPHome and 2023.4.1 Home Assistant
robchandhok
robchandhok commented on Apr 9, 2023
robchandhok
on Apr 9, 2023

I noticed in 2023.4.x (i'm on .2 now) the "add new entries" was reset to "on". Noticed new devices being added, so had to delete the integration and start over. FWIW.
disconn3ct
disconn3ct commented on May 9, 2023
disconn3ct
on May 9, 2023 · edited by disconn3ct

image

I also have only 2 or 3 devices.. (updated because 200 new devices showed in the past 4 weeks)
MichaelStruck
MichaelStruck commented on Jun 16, 2023
MichaelStruck
on Jun 16, 2023

This is on-going for me as well and wanted to track it by adding a comment. As with everyone else, even though this is clearly marked NOT to add new devices, they keep popping up. I am curious if it has to do with the theory that even existing devices are technically new devices if the appendix of the iBeacon (the last few digits) is always different, therefore for this to work properly you can't just limit this to existing devices. If that is the case, there should be some internal evaluation of the first section of the ibeacon, and then only allow it if it is already existing. Just my theory.
rlust
rlust commented on Jul 7, 2023
rlust
on Jul 7, 2023

Do we have any progress on a solution? same issue here.
ScottG489
ScottG489 commented on Jul 10, 2023
ScottG489
on Jul 10, 2023 · edited by ScottG489
Contributor

So the description says it shouldn't add new devices, but the name of the setting "Enable newly added entities" indicates that maybe it's still adding the devices, but then just disabling all that devices entities?

This has become a little more than an annoyance for me because it causes some nodes in Node Red to be really slow to open. I'm sure it's also not great for system performance.

Also, does anyone know of a way to mass-delete devices or entities?
ScottG489
ScottG489 commented on Jul 10, 2023
ScottG489
on Jul 10, 2023 · edited by ScottG489
Contributor

I did some testing with another integration (steam_online) and the behavior seemed to be that with "Enable newly added entities" disabled it still adds the entity, but with that entity disabled. I assume if a new devices is also normally added (not the case with steam_online so I can't confirm) then that device is also still added, but I don't think the device will be disabled.

I don't think this setting actually has anything to do with devices. If you look at the original frontend PR where this was added, the word "device" isn't actually used in the description. So I assume something was lost in translation whenever that was updated.

Update: Found where the wording was changed to "device", though no explanation as to why: home-assistant/frontend@29b697c#diff-e67939fd25c650222db710f18764d10ae69454b0e8ad680f5e10177c2db93ceaR762
ScottG489
ScottG489 commented on Jul 10, 2023
ScottG489
on Jul 10, 2023
Contributor

Spoke with a maintainer (bdraco) and he suggested the proper fix for this would be another system option (or augment the existing one) to get this desired behavior.
KameDomotics
KameDomotics commented on Jul 17, 2023
KameDomotics
on Jul 17, 2023

I have this problem too, I have many ibeacon devices not mine which are automatically detected by the system. Is there anything new to fix this issue? Thanks
bcutter
bcutter commented on Sep 22, 2023
bcutter
on Sep 22, 2023 · edited by bcutter

Even more confused people: https://community.home-assistant.io/t/mystery-ibeacon-tracker/471704

What about another "do not automatically add devices to the integration" system option?
Once one set up their devices, enable this and the collection of foreign devices is over.

For this integration it would be better being able to manually add devices. Then it would be an active task, no more drive-by surprises. I mean really, drive-by.
renini
renini commented on Dec 5, 2023
renini
on Dec 5, 2023

Anyone with a workaround for this?
bcutter
bcutter commented on Dec 5, 2023
bcutter
on Dec 5, 2023

I was meanwhile told it is illegal in some countries (e. g. the one I live in) to scan for foreign (bluetooth) devices. Separate projects like OpenMQTTGateway (OMG) for example have a whitelist/blacklist approach to fulfil this legal requirement.

At the same time, our iBeacon integrations constantly scan and collect all the crap out there. Interesting. Really interesting.
bschatzow
bschatzow commented on Jan 18, 2024
bschatzow
on Jan 18, 2024

How do you remove the ghost devices? I have over 500.
bkvargyas
bkvargyas commented on Jan 18, 2024
bkvargyas
on Jan 18, 2024

I ended up removing the iBeacon integration. A whitelist would have resolved it while ignoring all the other noise. I suspect it's low priority in fixing at this point in time.
hannemann
hannemann commented on Mar 20, 2024
hannemann
on Mar 20, 2024

    I ended up removing the iBeacon integration. A whitelist would have resolved it while ignoring all the other noise. I suspect it's low priority in fixing at this point in time.

How did you do that?
issue-triage-workflows
issue-triage-workflows commented on Jun 18, 2024
issue-triage-workflows
bot
on Jun 18, 2024

There hasn't been any activity on this issue recently. Due to the high number of incoming GitHub notifications, we have to clean some of the old issues, as many of them have already been resolved with the latest updates.
Please make sure to update to the latest Home Assistant version and check if that solves the issue. Let us know if that works for you by adding a comment 👍
This issue has now been marked as stale and will be closed if no further activity occurs. Thank you for your contributions.
issue-triage-workflows
added
stale
on Jun 18, 2024
bcutter
bcutter commented on Jun 18, 2024
bcutter
on Jun 18, 2024

#88111 (comment)
issue-triage-workflows
removed
stale
on Jun 18, 2024
KameDomotics
KameDomotics commented on Jun 18, 2024
KameDomotics
on Jun 18, 2024

Are there any updates on this issue? is it really that impossible to fix this problem or create a whitelist? Thank you
issue-triage-workflows
issue-triage-workflows commented on Sep 16, 2024
issue-triage-workflows
bot
on Sep 16, 2024

There hasn't been any activity on this issue recently. Due to the high number of incoming GitHub notifications, we have to clean some of the old issues, as many of them have already been resolved with the latest updates.
Please make sure to update to the latest Home Assistant version and check if that solves the issue. Let us know if that works for you by adding a comment 👍
This issue has now been marked as stale and will be closed if no further activity occurs. Thank you for your contributions.
issue-triage-workflows
added
stale
on Sep 16, 2024
bcutter
bcutter commented on Sep 16, 2024
bcutter
on Sep 16, 2024

    Are there any updates on this issue? is it really that impossible to fix this problem or create a whitelist? Thank you

Double that.
issue-triage-workflows
removed
stale
on Sep 16, 2024
elvenstof
elvenstof commented on Sep 20, 2024
elvenstof
on Sep 20, 2024

I am also still struggling with this problem.
codahq
codahq commented on Oct 22, 2024
codahq
on Oct 22, 2024

@bdraco any help here?
ScottG489
ScottG489 commented on Oct 22, 2024
ScottG489
on Oct 22, 2024
Contributor

Don't ping people directly like that. I also already mentioned above that I spoke with him and what his response was.
codahq
codahq commented on Oct 22, 2024
codahq
on Oct 22, 2024

He's the maintainer. He's hasn't spoken in the issue. It's been open for coming up on two years. I think it's warranted.
phdonnelly
mentioned this in 2 pull requests on Dec 2, 2024

    add option to ibeacon component to disable adding newly detected devices #132126
    add option to ibeacon component to disable adding newly detected devices #132127

issue-triage-workflows
issue-triage-workflows commented on Jan 20, 2025
issue-triage-workflows
bot
on Jan 20, 2025

There hasn't been any activity on this issue recently. Due to the high number of incoming GitHub notifications, we have to clean some of the old issues, as many of them have already been resolved with the latest updates.
Please make sure to update to the latest Home Assistant version and check if that solves the issue. Let us know if that works for you by adding a comment 👍
This issue has now been marked as stale and will be closed if no further activity occurs. Thank you for your contributions.
issue-triage-workflows
added
stale
on Jan 20, 2025
bcutter
bcutter commented on Jan 21, 2025
bcutter
on Jan 21, 2025

Let's play the unstale game like forever.

...until a mighty hero comes around the corner and fixes this.

As mentioned already in theory running this integration - how it works currently - is illegal in some countries.
issue-triage-workflows
removed
stale
on Jan 21, 2025
KameDomotics
KameDomotics commented on Jan 22, 2025
KameDomotics
on Jan 22, 2025 · edited by KameDomotics

I don't use this integration for many months, because I had hundreds of devices that weren't mine that were automatically added.
disconn3ct
disconn3ct commented on Jan 22, 2025
disconn3ct
on Jan 22, 2025

    Don't ping people directly like that. I also already mentioned above that I spoke with him and what his response was.

@bdraco @ScottG489 if you turn off stalebot, we will stop asking you to show up on time. The project installed a robot that enforces a clock. We are just asking you to honor your end of that "agreement" and either disable the robot on this verified bug, or be active during what your robot considers to be a reasonable amount of time.
home-assistant
locked and limited conversation to collaborators on Jan 22, 2025
bdraco
removed their assignment
on Jan 22, 2025
home-assistant
unlocked this conversation on Jan 22, 2025
bdraco
bdraco commented on Jan 22, 2025
bdraco
on Jan 22, 2025 · edited by bdraco
Member

I don't use ibeacons in production anymore. I removed myself as codeowner.

    Spoke with a maintainer (bdraco) and he suggested the proper fix for this would be another system option (or augment the existing one) to get this desired behavior.

I think this is still the best option for this case, but it requires a core architecture change to support it.
codahq
codahq commented on Jan 22, 2025
codahq
on Jan 22, 2025

    I don't use ibeacons in production anymore. I removed myself as codeowner.

        Spoke with a maintainer (bdraco) and he suggested the proper fix for this would be another system option (or augment the existing one) to get this desired behavior.

    I think this is still the best option for this case, but it requires a core architecture change to support it.

how does one get a core architecture change?
bdraco
bdraco commented on Jan 22, 2025
bdraco
on Jan 22, 2025
Member

https://developers.home-assistant.io/docs/core/entity?_highlight=architecture&_highlight=repo#changing-the-entity-model
bcutter
bcutter commented on Jan 22, 2025
bcutter
on Jan 22, 2025

Sounds like a long long way to go. Not only technical skills and efforts needed but also paper work and board decisions and discussions etc.

I think I might either just migrate away to a dedicated solution for my remaining devices or deep dive into "how to create an automation which disables every new device found by an integration". Genius how smart this is in 2025 😀
ScottG489
ScottG489 commented on Jan 23, 2025
ScottG489
on Jan 23, 2025
Contributor

You may find this helpful:
https://spook.boo/devices#disable-a-device
KameDomotics
KameDomotics commented on Jan 23, 2025
KameDomotics
on Jan 23, 2025

homeassistant.disable_device

This service is not available in my Home Assistant (2025.1.2)
brimmasch
brimmasch commented on Jan 23, 2025
brimmasch
on Jan 23, 2025

    homeassistant.disable_device

    This service is not available in my Home Assistant (2025.1.2)

right, you have to install spook which is a custom integration for home assistant.
KameDomotics
KameDomotics commented on Jan 23, 2025
KameDomotics
on Jan 23, 2025

        homeassistant.disable_device

        This service is not available in my Home Assistant (2025.1.2)

    right, you have to install spook which is a custom integration for home assistant.

But disabled is not deleted.
So there would be many disabled devices, it would be better to delete them.
Also how does the integration know which devices to delete?
brimmasch
brimmasch commented on Jan 23, 2025
brimmasch
on Jan 23, 2025 · edited by brimmasch

            homeassistant.disable_device

            This service is not available in my Home Assistant (2025.1.2)

        right, you have to install spook which is a custom integration for home assistant.

    But disabled is not deleted. So there would be many disabled devices, it would be better to delete them. Also how does the integration know which devices to delete?

it does not know which devices to disable. you will still have to write an automation with a trigger to detect when new devices were added and then use the service to disable them.

we still need a change to prevent the integration from creating the devices. it appears we will not get that change any time soon given that we have no active maintainer and even if we did the amount of work to do this (seemingly) easy thing is a lot.

so in the meantime, the suggestion (helpful) to use a separate custom integration (spook) to disable devices was just another way to clean up the mess created by this (ibeacon) integration.
phdonnelly
phdonnelly commented on Feb 13, 2025
phdonnelly
on Feb 13, 2025

Hmm; unfortunately my pull request to fix this was sitting so long I forgot about it and now it's closed. The proposed fix of disabling newly added entities is not sufficient for me; I live on a busy street and I get about 40-50 new devices per day so running without a patch results in literally hundreds of dead entities clogging up the UI.

TBH though I'm pretty sure it probably would not have passed review anyway, it's a pretty gross hack that just globally disables adding new devices from the integration; I wanted to do it properly by creating a whitelist didn't have the time.

I'm going to publish what I have in HACS anyway in case someone else needs a bandaid until this gets fixed properly.
phdonnelly
phdonnelly commented on Feb 13, 2025
phdonnelly
on Feb 13, 2025

Add custom repo in HACS: https://github.com/phdonnelly/ibeacon_ha_quiet

restart, goto settings->integrations->ibeacon tracker
click on configure
uncheck "Allow this integration to automatically create new devices"

If you want to add a new device, just temporarily enable the setting, wait until you see the new device, then turn it back off again.

Image
KameDomotics
KameDomotics commented on Feb 14, 2025
KameDomotics
on Feb 14, 2025

    Add custom repo in HACS: https://github.com/phdonnelly/ibeacon_ha_quiet

    restart, goto settings->integrations->ibeacon tracker
    click on configure
    uncheck "Allow this integration to automatically create new devices"

    If you want to add a new device, just temporarily enable the setting, wait until you see the new device, then turn it back off again.

    Image

I installed your custom, but unfortunately it still adds unknown devices
phdonnelly
phdonnelly commented on Feb 14, 2025
phdonnelly
on Feb 14, 2025

Hmm, looks like I only stopped beacons with unique addresses and not ones with random beacons from being added. I'll tweak the code to cover both cases and add some extra logging as well
phdonnelly
phdonnelly commented on Feb 14, 2025
phdonnelly
on Feb 14, 2025 · edited by phdonnelly

OK, so I took a look at the existing code and the way random mac beacons are handled is slightly different; they are not loaded into a dictionary by the integration at startup, so I don't have an easy way to determine what is a new vs existing random mac beacon. As a quick workaround I've just disabled random mac beacons from being added or updated at all.

Obviously not great if you happen to use those types of ibeacons, but if you don't then the latest build should do the trick. If you're still having a problem submit an issue here https://github.com/phdonnelly/ibeacon_ha_quiet/issues with your home assistant log (with ibeacon debug logging enabled) and I'll try and take a look.

Edit, also just to be sure; you've un-ticked the checkbox in the settings correct? It defaults to on to keep the existing behaviour.
KameDomotics
KameDomotics commented on Feb 14, 2025
KameDomotics
on Feb 14, 2025

    Hmm, looks like I only stopped beacons with unique addresses and not ones with random beacons from being added. I'll tweak the code to cover both cases and add some extra logging as well

Thanks, you are really very good! Anyway, I tried to restart the host (Raspberry), which I had not done before. No new unknown beacons have been added for 7 hours.
I'm still using the first version of your custom, I'll try it for a few days and see if it works properly.

Thanks for your great work
frenck
added the
Bug
issue type on Mar 28, 2025
raveit65
raveit65 commented on Apr 9, 2025
raveit65
on Apr 9, 2025

    Edit, also just to be sure; you've un-ticked the checkbox in the settings correct? It defaults to on to keep the existing behaviour.

Thanks, this works really great for me. I was able to ban about 150 ibeacons around my flat which aren't mine :-)
....cool job.
issue-triage-workflows
issue-triage-workflows commented on Jul 8, 2025
issue-triage-workflows
bot
on Jul 8, 2025

There hasn't been any activity on this issue recently. Due to the high number of incoming GitHub notifications, we have to clean some of the old issues, as many of them have already been resolved with the latest updates.
Please make sure to update to the latest Home Assistant version and check if that solves the issue. Let us know if that works for you by adding a comment 👍
This issue has now been marked as stale and will be closed if no further activity occurs. Thank you for your contributions.
issue-triage-workflows
added
stale
on Jul 8, 2025
raveit65
raveit65 commented on Jul 8, 2025
raveit65
on Jul 8, 2025

Sorry, this isn't fixed. Please start working on it instead of trying to close it -_-
issue-triage-workflows
removed
stale
on Jul 8, 2025
brimmasch
brimmasch commented on Jul 8, 2025
brimmasch
on Jul 8, 2025

it's weird that we can't get any traction on this bug from anybody on the project. it's been opened in various flavors quite a few times, it plagues quite a few users and it's a wildly horrible user experience. i saw something posted during the week of wth about it but it didn't grab enough attention.
raveit65
raveit65 commented on Jul 8, 2025
raveit65
on Jul 8, 2025

@frenck
Why not using https://github.com/phdonnelly/ibeacon_ha_quiet ?
This is dirty and simple, but it does what users want!
KameDomotics
KameDomotics commented on Jul 16, 2025
KameDomotics
on Jul 16, 2025

    @frenck
    Why not using https://github.com/phdonnelly/ibeacon_ha_quiet ?
    This is dirty and simple, but it does what users want!

I'm using this modified version. It works very well, the creator did a great job. It's a shame the integration developer hasn't fixed the bug in all these years.
nordeep
nordeep commented on Sep 3, 2025
nordeep
on Sep 3, 2025
Contributor

I found myself in the same situation. My tracker creates about 50 devices per day, each with 4 entities, totaling around 200 entities per day.
I noticed it after the Home Assistant Companion App on my pad started running extremely slowly. It turned out that I had 2000 iBeacon devices, while I'm actually only interested in 3 of them.
Even though we have the "Enable newly added entities" option disabled, it only disables the entities but does not prevent their creation.
There should be another option that "Prohibits the registration of new iBeacon devices" in the system. Similar to Z2M, where we can block the coordinator from registering new Zigbee devices.
This is actually a significant issue, and many users are unaware that they have so many iBeacon devices created, which is why their Home Assistant interface is running slowly.
brimmasch
brimmasch commented on Sep 3, 2025
brimmasch
on Sep 3, 2025

@phdonnelly sorry for the direct ping but i visited home assistant today and i noticed that i had a lot of devices created again. this is with allow the integration to create new devices turned off. if i have a esp32 bluetooth relay, is it ignoring this setting and creating devices anyway because of something the relay does?
Image
vint66
vint66 commented on Sep 3, 2025
vint66
on Sep 3, 2025

+1
Thought I think this might be exactly how it works. I have unchecked system option 'enable entities' for iBeacon and only add my UUID manually.
But it won't prevent from adding device. It won't have any entity enabled though, so it should not be polling. But it is still polluting UI and if those are hundreds it gets really busy.
phdonnelly
phdonnelly commented on Sep 4, 2025
phdonnelly
on Sep 4, 2025 · edited by phdonnelly

@brimmasch Hmm; I'm not sure I don't utilize the esp32 bluetooth relay feature so i never tested it; I would assume they operate the same but maybe not.

If you create an issue on https://github.com/phdonnelly/ibeacon_ha_quiet/issues, enable debug logging for the custom component, reload it, wait a few min, then disable it and attach that log I can take a look.
nordeep
nordeep commented on Sep 8, 2025
nordeep
on Sep 8, 2025
Contributor

Several days have passed, and once again there are 200+ devices and 1000+ entities. And my iPad again cannot load the Home Assistant page.
Image

The problem is that all objects are transmitted during the loading of the Home Assistant web interface, which we can observe in the DevTools Console.
The screenshot shows the loading of an array of 5325 elements, where each element represents an entity. Even! if it is Disabled in Home Assistant.
Also visible is the loading of an array of 544 elements, which I assume are Devices and similar items.
Image Image Image

The reality is that the larger these arrays are, the more difficult they are for the web browser to process. On less powerful devices, the processing fails, and the Home Assistant Companion App freezes.

@phdonnelly, would you mind submitting the Pull Request again - #132127 ? As I understand it, this Pull Request lacked sufficient explanation for the code owner. I am ready to join in and provide diagnostic data from my side.
nordeep
nordeep commented on Sep 15, 2025
nordeep
on Sep 15, 2025
Contributor

A week has passed: +240 devices and +2200 entities. And the worst part is, there's no way to delete them in bulk, only one by one.
Image
bcutter
bcutter commented on Sep 15, 2025
bcutter
on Sep 15, 2025 · edited by bcutter

Oh wow. For me only 3 new devices. Some time ago I switched from deleting to disabling them, that way when they are around again they're not discovered as new devices again - ideally.

image

In your case (huge amount of devices) I would have ditched the integration a long time ago.

This way I "only" likely violate local laws by scanning foreign devices (allowlist shall be used - which is basically "stop adding new devices" setting). But no performance or increased maintenance issues.
phdonnelly
phdonnelly commented on Sep 15, 2025
phdonnelly
on Sep 15, 2025

    @phdonnelly, would you mind submitting the Pull Request again - #132127 ? As I understand it, this Pull Request lacked sufficient explanation for the code owner. I am ready to join in and provide diagnostic data from my side.

Hi @nordeep unfortunately the pull request is highly unlikely to be accepted.

Honestly it is a very ugly patch; I threw this together because it fixes the problem and its good enough for me, but it does not do it correctly. The correct solution would be to allow the user to build an allowlist similar to the one the integration uses for anonymous/nameless trackers; I tried to do this for several days and could not get the config_flow section to work correctly, so I finally just used a giant hammer to add a global killswitch to the integration; it technically works, but has several issues e.g. internally the integration is actually still tracking every beacon that it sees, it just doesn't create entities for them, it doesn't work at all for devices with random mac devices, etc.

Have you tried installing the custom component version as a workaround for now?
KameDomotics
KameDomotics commented on Sep 15, 2025
KameDomotics
on Sep 15, 2025

    Hi @nordeep unfortunately the pull request is highly unlikely to be accepted.

    Honestly it is a very ugly patch; I threw this together because it fixes the problem and its good enough for me, but it does not do it correctly. The correct solution would be to allow the user to build an allowlist similar to the one the integration uses for anonymous/nameless trackers; I tried to do this for several days and could not get the config_flow section to work correctly, so I finally just used a giant hammer to add a global killswitch to the integration; it technically works, but has several issues e.g. internally the integration is actually still tracking every beacon that it sees, it just doesn't create entities for them, it doesn't work at all for devices with random mac devices, etc.

    Have you tried installing the custom component version as a workaround for now?

I've been using your patch since you created it, and it works perfectly. You did a really great job!

I don't think the official integration will ever be fixed; it's probably not even supported by the developer anymore.
eigenphase
eigenphase commented on Sep 15, 2025
eigenphase
on Sep 15, 2025

Ok, I'm joining the party. Just got started with BLE a few days ago. I saw this issue is ongoing since 2023, 2-1/2 years ... and still not fixed?? It's open source software, so I don't want to be demanding but if such an obvious bug that haunts so many people is not fixed, then it should not be part of HA Core. Really frustrating.
nordeep
nordeep commented on Sep 16, 2025
nordeep
on Sep 16, 2025
Contributor

@bcutter Actually, I'm using this integration. I have several iBeacon key fobs for my front door keys, and they work with a Smart Lock. But hundreds of devices per week (I live on a busy street) are killing me.

@phdonnelly I haven't added your custom component. I'm sure it would work as intended. But we're all in the same boat; the device registration limit should be handled in the core of the component.
I've looked at your patch; perhaps a killswitch is exactly what we need.
I don't know of any other good way to get the attention of the code owner.
nordeep
nordeep commented on Sep 22, 2025
nordeep
on Sep 22, 2025
Contributor

Sorry to bother everyone. Another week has passed: +100 devices and +1000 entities
Image
issue-triage-workflows
issue-triage-workflows commented on Dec 21, 2025
issue-triage-workflows
bot
on Dec 21, 2025

There hasn't been any activity on this issue recently. Due to the high number of incoming GitHub notifications, we have to clean some of the old issues, as many of them have already been resolved with the latest updates.
Please make sure to update to the latest Home Assistant version and check if that solves the issue. Let us know if that works for you by adding a comment 👍
This issue has now been marked as stale and will be closed if no further activity occurs. Thank you for your contributions.
issue-triage-workflows
added
stale
on Dec 21, 2025
raveit65
raveit65 commented on Dec 21, 2025
raveit65
on Dec 21, 2025

Issue isn't fixed, sadly no reaction from home-assistant team which is another issue.....
github-actions
removed
stale
on Dec 21, 2025
nordeep
nordeep commented on Dec 22, 2025
nordeep
on Dec 22, 2025
Contributor

Unfortunately, I have to agree with raveit65, there is no reaction from the home-assistant team.
In my case, the integration has already discovered 1631 devices and 8155 entities. My desktop web browser struggles to open the integration page.
Image
codahq
codahq commented on Dec 22, 2025
codahq
on Dec 22, 2025

It's kind of wild at this point. There probably aren't many bugs that were opened in 2023 that haven't been either closed as not fixable or resolved, especially with this many comments. No one from the project has given this the time of day.
eigenphase
eigenphase commented on Dec 23, 2025
eigenphase
on Dec 23, 2025

This is where I just don't understand why some integrations are integrated in Home Assistant, rather than HACS. This looks completely abandoned to me, how is it still part of the HA core distribution?
KameDomotics
KameDomotics commented on Dec 25, 2025
KameDomotics
on Dec 25, 2025

There is a custom iBeacon integration on HACS that fixes the problem with the native Home Assistant integration.

I have been using it for many months and it works really well.

I really don't understand why the Home Assistant developers don't apply this fix to the official integration as well.
bcutter
bcutter commented on Dec 25, 2025
bcutter
on Dec 25, 2025 · edited by bcutter

Yep. I don't know the HACS version but looking at this issue and its (lack of) maintenance related to a long-term major design issue it simply damages the value proposition of Home Assistants core integrations.

When a custom integration is ahead of core integrations (usually the case in terms of features and release speed) you really need to wonder why unmaintained core integrations exist at all (dramatically speaking, of course in general stability and maintenance related to Core changes are the usual advantage).
thatso
thatso commented on Dec 25, 2025
thatso
on Dec 25, 2025
Contributor

Just to confirm: there are several core components where the so-called project owners don't give a sh*t about looking into issues or seemingly have silently abandoned their responsibilities a long time ago. The term "open source thrives on participation" gets stale very fast if nobody cares about reported bugs.
codahq
codahq commented on Dec 25, 2025
codahq
on Dec 25, 2025

    Yep. I don't know the HACS version but looking at this issue and its (lack of) maintenance related to a long-term major design issue it simply damages the value proposition of Home Assistants core integrations.

    When a custom integration is ahead of core integrations (usually the case in terms of features and release speed) you really need to wonder why unmaintained core integrations exist at all (dramatically speaking, of course in general stability and maintenance related to Core changes are the usual advantage).

in this particular case, not only does it reflect poorly on the entire project and the value proposition of core integrations, it shows how very large (extremely large) open source projects often don't scale well. i'm surprised this project hasn't fragmented into multiple forks yet. i've seen a few times where bad decisions or bad behavior could have pushed a group to break off.

either way, the existing integration should probably be jettisoned into the sun. it's unusable. it should be fixed so it's usable or relinquished so somebody else will fill the gap.

@phdonnelly is the only silver lining here. thank you for your patch. regardless of how you did it, it works. i've had only one device for several months, no new unwanted devices and it's great.
eigenphase
eigenphase commented on Dec 25, 2025
eigenphase
on Dec 25, 2025

@KameDomotics would you mind sharing the link to the version you’re referring to?
Strangely I’m not able to find an iBeacon extension in HACS
KameDomotics
KameDomotics commented on Dec 26, 2025
KameDomotics
on Dec 26, 2025 · edited by KameDomotics

    @KameDomotics would you mind sharing the link to the version you’re referring to?
    Strangely I’m not able to find an iBeacon extension in HACS

@eigenphase

iBeacon HA Quiet
nordeep
nordeep commented on Jan 4
nordeep
on Jan 4
Contributor

I finally gave up and switched to the custom iBeacon HA Quiet integration by @phdonnelly.
The last straw was that my Wear OS watch could no longer load HA app. Before removing the built-in integration, it had about 1,800 devices and 9,000 entities.
bcutter
bcutter commented on Jan 6
bcutter
on Jan 6 · edited by bcutter

Where can one request to remove an integration from core? For HACS custom integrations this is pretty easy.

Following old (one freaking year... more than 365 days...) #132127 (review) (which rejection lead to the creation of the custom iBeacon HA Quiet integration) it seems like there was a misunderstanding. Disabling "Enable newly added entities" still adds new devices, but only disables their entities. We want and need to block the adding of NEW DEVICES. Entities != Devices. So the closure reason for that PR was invalid.

Notable comments of @phdonnelly (and yes, a proper allowlist would indeed be the perfect solution):

    ibeacon keeps adding New Devices even if it's configured not to do so #88111 (comment)
    ibeacon keeps adding New Devices even if it's configured not to do so #88111 (comment)

I also switched to this custom integration now and used the chance to cleanup orphaned, foreign devices:

    123 devices with 615 entities --> 3 device with 15 entities
    (usually 2 devices, one is impossible to delete Deletion of device not possible: Failed to remove device entry, rejected by integration phdonnelly/ibeacon_ha_quiet#6)
    That reduced quite some trash from the system.

Now interesting to watch how the integration behaves in the next days and weeks (will it discover new foreign devices?).

Update: It still detects devices, even the Allow this integration to automatically create new devices. switch is disabled. ☹️
phillipjws
phillipjws commented last week
phillipjws
last week

Hi maintainers, our group is planning to work on this issue as part of a university software engineering project.

If this issue is available, could it be assigned to me (or marked as in progress for our group)?
We expect to open a PR soon and will post progress updates here.

Thanks.
phillipjws
Add a comment
new Comment
Markdown input: edit mode selected.
Remember, contributions to this repository should follow its contributing guidelines, security policy, code of conduct and Support.
Metadata
Assignees
No one assigned

Labels
integration: ibeacon
Type
Bug
Projects
No projects
Milestone
No milestone

Relationships
None yet

Development

Notifications

You're receiving notifications because you're subscribed to this thread.
Participants
@frenck
@disconn3ct
@arigit
@bdraco
@phdonnelly
Issue actions

Footer
© 2026 GitHub, Inc.
Footer navigation

    Terms
    Privacy
    Security
    Status
    Community
    Docs
    Contact

ibeacon keeps adding New Devices even if it's configured not to do so · Issue #88111 · home-assistant/core