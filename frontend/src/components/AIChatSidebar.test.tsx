import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AIChatSidebar } from "@/components/AIChatSidebar";
import { initialData } from "@/lib/kanban";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("AIChatSidebar", () => {
  it("submits a question, renders the response, and updates the board", async () => {
    const updatedBoard = {
      ...initialData,
      cards: {
        ...initialData.cards,
        "card-ai": { id: "card-ai", title: "AI task", details: "Created" },
      },
    };
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        message: "I created that task.",
        operations: [{ type: "create_card" }],
        board: updatedBoard,
      }),
    });
    const onBoardUpdate = vi.fn();

    render(<AIChatSidebar onBoardUpdate={onBoardUpdate} />);
    await userEvent.type(screen.getByLabelText("Ask the assistant"), "Create a task");
    await userEvent.click(screen.getByRole("button", { name: "Send to assistant" }));

    expect(await screen.findByText("I created that task.")).toBeVisible();
    expect(onBoardUpdate).toHaveBeenCalledWith(updatedBoard);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/ai/chat",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("shows a provider error and keeps the composer usable", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "The AI provider timed out. Try again shortly." }),
    });

    render(<AIChatSidebar onBoardUpdate={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Ask the assistant"), "Help");
    await userEvent.click(screen.getByRole("button", { name: "Send to assistant" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("timed out");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Send to assistant" })).toBeEnabled();
    });
  });
});
