<!--
  You are amazing! Thanks for contributing to our project!
  Please, DO NOT DELETE ANY TEXT from this template! (unless instructed).
-->
## Breaking change
<!--
  If your PR contains a breaking change for existing users, it is important
  to tell them what breaks, how to make it work again and why we did this.
  This piece of text is published with the release notes, so it helps if you
  write it towards our users, not us.
  Note: Remove this section if this PR is NOT a breaking change.
-->


## Proposed change
<!--
  Describe the big picture of your changes here to communicate to the
  maintainers why we should accept this pull request. If it fixes a bug
  or resolves a feature request, be sure to link to that issue in the
  additional information section.
-->

Add device availability tracking and automatic camera re-discovery to the ONVIF integration.

### Problem

Currently, `ONVIFDevice.available` is set to `True` during `__init__` and **never changed**. This means:

1. When a camera goes offline, entities never show as unavailable in HA
2. When cameras behind an NVR temporarily disconnect, they are never rediscovered because profiles are fetched once during setup and never refreshed
3. Cached RTSP stream URIs become stale after a camera reconnects with a different address

This particularly affects NVR setups where individual camera channels can go offline and come back independently of the NVR itself.

### Solution

Hook into the existing PullPoint polling loop (which already runs as a heartbeat) to track device availability:

- **`device.py`**: Add `async_mark_available()`, `async_mark_unavailable()`, and `async_refresh_profiles()` to `ONVIFDevice`
- **`event_manager.py`**: Track consecutive PullPoint failures. After 3 consecutive failures, mark device unavailable. On successful pull after failures, mark available and trigger profile re-fetch
- **`camera.py`**: Register as an EventManager listener to clear cached `_stream_uri` when the device transitions from unavailable → available

When profiles change after reconnection (e.g., NVR added/removed a camera channel), `async_refresh_profiles()` triggers `config_entries.async_reload()` which recreates entities.

The `onvif_device` parameter is optional in `EventManager.__init__()` for backward compatibility.

### Why PullPoint?

For cameras behind NVRs, the PullPoint event subscription is the **only** connection path to detect availability — DHCP and WS-Discovery don't see cameras behind an NVR. The PullPoint loop already polls at ~60s intervals with error handling, making it the natural heartbeat.

## Type of change
<!--
  What type of change does your PR introduce to Home Assistant?
  NOTE: Please, check only 1! box!
  If your PR requires multiple boxes to be checked, you'll most likely need to
  split it into multiple PRs. This makes things easier and faster to code review.
-->

- [ ] Dependency upgrade
- [x] Bugfix (non-breaking change which fixes an issue)
- [ ] New integration (thank you!)
- [ ] New feature (which adds functionality to an existing integration)
- [ ] Deprecation (breaking change to happen in the future)
- [ ] Breaking change (fix/feature causing existing functionality to break)
- [ ] Code quality improvements to existing code or addition of tests

## Additional information
<!--
  Details are important, and help maintainers processing your PR.
  Please be sure to fill out additional details, if applicable.
-->

- This PR fixes or closes issue: fixes #91398
- This PR is related to issue: #137453, #76156
- Link to documentation pull request: N/A (no docs changes needed)
- Link to developer documentation pull request: N/A
- Link to frontend pull request: N/A

## Checklist
<!--
  Put an `x` in the boxes that apply. You can also fill these out after
  creating the PR. If you're unsure about any of them, don't hesitate to ask.
  We're here to help! This is simply a reminder of what we are going to look
  for before merging your code.
-->

- [x] The code change is tested and works locally.
- [ ] Local tests pass. **Your PR cannot be merged unless tests pass**
- [x] There is no commented out code in this PR.
- [x] I have followed the [development checklist][dev-checklist]
- [x] I have followed the [perfect PR recommendations][perfect-pr]
- [x] The code has been formatted using Ruff (`ruff format homeassistant tests`)
- [x] Tests have been added to verify that the new code works.

If user exposed functionality or configuration variables are added/changed:

- [ ] Documentation added/updated for [www.home-assistant.io][docs-repository]

If the code communicates with devices, web services, or third-party tools:

- [x] The [manifest file][manifest-docs] is up to date with all [supported brands](https://brands.home-assistant.io/).
- [ ] New or updated dependencies have been added to `requirements_all.txt`.
  `python3 -m script.gen_requirements_all`.
- [ ] For the updated dependencies - Loss of a connected device, service, or third-party tool [doesn't block startup or setup](https://developers.home-assistant.io/docs/integration_setup_failures). If it does, a `filtered_timeout` should be used.

<!--
  This project is very active and we have a high turnover of pull requests.

  Unfortunately, the number of incoming pull requests is higher than what our
  reviewers can review and merge so there is a long backlog of pull requests
  waiting for review. You can help here!

  By reviewing another pull request, you will help raise the code quality of
  that pull request and the final review will be faster. This way the general
  pace of pull request reviews will go up and your wait time will go down.

  When picking a PR to review, try to choose a smaller one so you can finish
  it in a reasonable time.

  Thanks for helping out!
-->

To help with the load of incoming pull requests:

- [ ] I have reviewed two other [open pull requests][prs] in this repository.

[prs]: https://github.com/home-assistant/core/pulls?q=is%3Aopen+is%3Apr+-author%3A%40me+-draft%3Atrue+-label%3Awaiting-for-upstream+sort%3Acreated-desc+review%3Anone+-status%3Afailure

<!--
  Thank you for contributing <3

  Below, some useful links you could explore:
-->
[dev-checklist]: https://developers.home-assistant.io/docs/development_checklist/
[manifest-docs]: https://developers.home-assistant.io/docs/creating_integration_manifest/
[quality-scale]: https://developers.home-assistant.io/docs/integration_quality_scale_index/
[docs-repository]: https://github.com/home-assistant/home-assistant.io
[perfect-pr]: https://developers.home-assistant.io/docs/review-process/#creating-the-perfect-pr
