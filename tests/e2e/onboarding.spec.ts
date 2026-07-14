import { expect, test } from "@playwright/test";

test("fresh instance redirects to onboarding and renders the UI", async ({
  page,
}) => {
  await page.goto("/");

  // A fresh (un-onboarded) instance redirects the root to the onboarding page.
  await expect(page).toHaveURL(/\/onboarding\.html/);
  await expect(page.locator("ha-onboarding")).toBeVisible();
});
