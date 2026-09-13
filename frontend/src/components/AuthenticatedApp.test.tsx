import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthenticatedApp } from "@/components/AuthenticatedApp";
import { initialData } from "@/lib/kanban";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("AuthenticatedApp", () => {
  it("shows the sign-in form when there is no session", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false });

    render(<AuthenticatedApp />);

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeVisible();
    expect(screen.getByLabelText("Username")).toBeVisible();
  });

  it("opens the board after a successful login", async () => {
    fetchMock
      .mockResolvedValueOnce({ ok: false })
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({ ok: true, json: async () => initialData });

    render(<AuthenticatedApp />);
    await screen.findByRole("heading", { name: "Welcome back" });

    await userEvent.type(screen.getByLabelText("Username"), "user");
    await userEvent.type(screen.getByLabelText("Password"), "password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
    });
  });
});
