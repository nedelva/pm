"use client";

import { useState, type FormEvent } from "react";
import { chatWithAI, type ChatMessage } from "@/lib/api";
import type { BoardData } from "@/lib/kanban";

type AIChatSidebarProps = {
  onBoardUpdate: (board: BoardData) => void;
};

export const AIChatSidebar = ({ onBoardUpdate }: AIChatSidebarProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || isPending) return;

    const history = messages.slice(-20);
    setError(null);
    setMessages((current) => [...current, { role: "user", content: trimmedQuestion }]);
    setIsPending(true);

    try {
      const result = await chatWithAI(trimmedQuestion, history);
      onBoardUpdate(result.board);
      setQuestion("");
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.message },
      ]);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The assistant could not respond."
      );
    } finally {
      setIsPending(false);
    }
  };

  return (
    <aside
      className="flex min-h-[520px] flex-col rounded-[28px] border border-[var(--stroke)] bg-[var(--navy-dark)] p-5 text-white shadow-[var(--shadow)] lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)]"
      data-testid="ai-chat"
    >
      <div className="flex items-start justify-between gap-4 border-b border-white/15 pb-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--accent-yellow)]">
            Workspace assistant
          </p>
          <h2 className="mt-2 font-display text-2xl font-semibold">Ask the board</h2>
          <p className="mt-2 text-sm leading-6 text-white/65">
            Ask questions or describe a board change.
          </p>
        </div>
        <span className="mt-1 h-3 w-3 rounded-full bg-[var(--accent-yellow)] shadow-[0_0_0_5px_rgba(236,173,10,0.14)]" />
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto py-5" aria-live="polite">
        {messages.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm leading-6 text-white/70">
            Try “What is in the backlog?” or “Create a card for the launch review.”
          </div>
        ) : null}
        {messages.map((message, index) => (
          <div
            className={message.role === "user" ? "flex justify-end" : "flex justify-start"}
            key={`${message.role}-${index}`}
          >
            <p
              className={
                message.role === "user"
                  ? "max-w-[90%] rounded-2xl rounded-br-md bg-[var(--accent-yellow)] px-4 py-3 text-sm font-semibold text-[var(--navy-dark)]"
                  : "max-w-[90%] rounded-2xl rounded-bl-md bg-white/10 px-4 py-3 text-sm leading-6 text-white/85"
              }
            >
              {message.content}
            </p>
          </div>
        ))}
        {isPending ? (
          <p className="text-sm text-white/55" role="status">
            Thinking...
          </p>
        ) : null}
      </div>

      {error ? (
        <p className="mb-3 rounded-xl border border-red-200/30 bg-red-400/10 px-3 py-2 text-sm text-red-100" role="alert">
          {error}
        </p>
      ) : null}

      <form className="border-t border-white/15 pt-4" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="ai-question">
          Ask the assistant
        </label>
        <textarea
          id="ai-question"
          className="min-h-24 w-full resize-none rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none placeholder:text-white/40 focus:border-[var(--accent-yellow)]"
          placeholder="Ask something about your board..."
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <button
          className="mt-3 w-full rounded-2xl bg-[var(--accent-yellow)] px-4 py-3 text-sm font-bold text-[var(--navy-dark)] transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
          type="submit"
          disabled={isPending || !question.trim()}
        >
          {isPending ? "Waiting for assistant..." : "Send to assistant"}
        </button>
      </form>
    </aside>
  );
};
