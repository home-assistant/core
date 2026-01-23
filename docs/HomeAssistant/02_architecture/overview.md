---
title: "Architecture overview"
---

Home Assistant provides a platform for home control and home automation. Home Assistant is not just an application: it's an embedded system that provides an experience like other consumer off-the-shelf products: onboarding, configuration and updating is all done via an easy to use interface.

- The [operating system](operating-system.md) provides the bare minimal Linux environment to run Supervisor and Core.
- The [Supervisor](supervisor.md) manages the operating system.
- The [Core](architecture/core.md) interacts with the user, the supervisor and IoT devices & services.

<img
  src='/img/en/architecture/full.svg'
  alt='Full picture of Home Assistant'
/>

## Running parts of the stack

Users have different requirements for what they want from a home automation platform. That's why it is possible to run only part of the Home Assistant stack. For more information, see the [installation instructions](https://www.home-assistant.io/installation/).
