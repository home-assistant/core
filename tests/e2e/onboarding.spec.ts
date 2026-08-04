import { expect, test } from "@playwright/test";

test("fresh instance redirects to onboarding and renders the UI", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page).toHaveURL(/\/onboarding\.html/);
  await expect(page.locator("ha-onboarding")).toBeVisible();
});
