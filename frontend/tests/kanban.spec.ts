import { expect, test } from "@playwright/test";
import { initialData } from "../src/lib/kanban";

const signIn = async (page: Parameters<Parameters<typeof test>[1]>[0]["page"]) => {
  await page.goto("/");
  await page.waitForSelector('input[autocomplete="username"], h1');
  const username = page.getByLabel("Username");
  if ((await username.count()) > 0) {
    await username.fill("user");
    await page.getByLabel("Password").fill("password");
    await page.getByRole("button", { name: "Sign in" }).click();
  }
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
};

test("loads the kanban board", async ({ page }) => {
  await signIn(page);
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("adds a card to a column", async ({ page }) => {
  await signIn(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  const cardTitle = `Playwright card ${Date.now()}`;
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill(cardTitle);
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText(cardTitle)).toBeVisible();
});

test("moves a card between columns", async ({ page }) => {
  await signIn(page);
  const card = page.getByTestId("card-card-1");
  const targetColumn = page.getByTestId("column-col-review");
  const cardBox = await card.boundingBox();
  const columnBox = await targetColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }

  await page.mouse.move(
    cardBox.x + cardBox.width / 2,
    cardBox.y + cardBox.height / 2
  );
  await page.mouse.down();
  await page.mouse.move(
    columnBox.x + columnBox.width / 2,
    columnBox.y + 120,
    { steps: 12 }
  );
  await page.mouse.up();
  await expect(targetColumn.getByTestId("card-card-1")).toBeVisible();
});

test("rejects invalid credentials", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("wrong");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByText("Invalid username or password")).toBeVisible();
});

test("logs out of the workspace", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "Log out" }).click();

  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});

test("edits a card and keeps the change after refresh", async ({ page }) => {
  await signIn(page);
  const card = page.getByTestId("card-card-1");
  await card.getByRole("button", { name: /^Edit / }).click();
  await card.getByLabel(/title for/i).fill("Persisted card edit");
  await card.getByLabel(/details for/i).fill("Saved through the board API");
  await card.getByRole("button", { name: "Save" }).click();

  await expect(page.getByText("Persisted card edit")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Persisted card edit")).toBeVisible();
});

test("chat response refreshes the board", async ({ page }) => {
  await page.route("**/api/ai/chat", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        message: "I created an AI task.",
        operations: [{ type: "create_card" }],
        board: {
          ...initialData,
          cards: {
            ...initialData.cards,
            "card-ai": { id: "card-ai", title: "AI launch task", details: "Created from chat" },
          },
          columns: initialData.columns.map((column) =>
            column.id === "col-backlog"
              ? { ...column, cardIds: [...column.cardIds, "card-ai"] }
              : column
          ),
        },
      }),
    });
  });

  await signIn(page);
  const chat = page.getByTestId("ai-chat");
  await chat.getByLabel("Ask the assistant").fill("Create a launch task");
  await chat.getByRole("button", { name: "Send to assistant" }).click();

  await expect(chat.getByText("I created an AI task.")).toBeVisible();
  await expect(page.getByText("AI launch task")).toBeVisible();
});
