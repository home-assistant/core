---
title: "Catching up with reality"
---

If it's taking a while to develop your feature, and you want to catch up with what's in the current Home Assistant `dev` branch, you can either use `git merge` or `git rebase`.
Below you can find instructions on how to do it using `git merge`. This will pull the latest Home Assistant changes locally, and merge them into your branch by creating a merge commit.

You should have added an additional `remote` after you clone your fork. If you did not, do it now before proceeding:

```shell
git remote add upstream https://github.com/home-assistant/core.git
```

```shell
# Run this from your feature branch
git fetch upstream dev  # to fetch the latest changes into a local dev branch
git merge upstream/dev  # to put those changes into your feature branch before your changes
```

If git detects any conflicts do the following to solve them:

1. Use `git status` to see the file with the conflict; edit the file and resolve the lines between `<<<< | >>>>`
2. Add the modified file: `git add <file>` or `git add .`
3. Finish the merge by committing it (you can leave the default merge commit message unchanged): `git commit`

Finally, just push your changes as normal:

```shell
# Run this from your feature branch
git push
```

If that command fails, it means that new work was pushed to the branch from either you or another contributor since your last update. In that case, just pull them into your local branch, solve any conflicts and push everything again:

```shell
# Run this from your feature branch
git pull --no-rebase
git push
```


Other workflows are covered in detail in the [Github documentation](https://docs.github.com/get-started/quickstart/fork-a-repo).
