---
title: "Submit your work"
---

:::tip
Always base your Pull Requests off of the current **`dev`** branch, not `master`.
:::

Submit your improvements, fixes, and new features to Home Assistant one at a time, using GitHub [Pull Requests](https://docs.github.com/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests). Here are the steps:

1. From your fork's dev branch, create a new branch to hold your changes:

    `git checkout -b some-feature`

2. Make your changes, create a [new platform](creating_platform_index.md), develop a [new integration](creating_component_index.md), or fix [issues](https://github.com/home-assistant/core/issues).

3. [Test your changes](development_testing.md) and check for style violations.  
    Consider adding tests to ensure that your code works.

4. If everything looks good according to these [musts](development_checklist.md), commit your changes:

    `git add .`

    `git commit -m "Add some feature"`

     - Write a meaningful commit message and not only something like `Update` or `Fix`.
     - Use a capital letter to start with your commit message and do not finish with a full-stop (period).
     - Don't prefix your commit message with `[bla.bla]` or `platform:`.
     - Write your commit message using the imperative voice, e.g. `Add some feature` not `Adds some feature`.
     

5. Push your committed changes back to your fork on GitHub:

    `git push origin HEAD`

6. Follow [these steps](https://docs.github.com/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request) to create your pull request.

    - On GitHub, navigate to the [main page of the Home Assistant repository](https://github.com/home-assistant/core).
    - In the "Branch" menu, choose the branch that contains your commits (from your fork).
    - To the right of the Branch menu, click **New pull request**.
    - Use the base branch dropdown menu to select the branch you'd like to merge your changes into, then use the compare branch drop-down menu to choose the topic branch you made your  changes in. Make sure the Home Assistant branch matches with your forked branch (`dev`) else you will propose ALL commits between branches.
    - Type a title and complete the provided template for your pull request.
    - Click **Create pull request**.

7. Check for comments and suggestions on your pull request and keep an eye on the [CI output](https://github.com/home-assistant/core/actions).

:::info
If this is your first time submitting a pull request, the CI won't run until a maintainer approves running it. Just wait, a maintainer will eventually come by and approve it.
:::
