"use client";

import { FormEvent, useEffect, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

type SessionState =
  | { status: "loading" }
  | { status: "authenticated"; username: string }
  | { status: "unauthenticated" };

const apiUrl = (path: string) => `${API_BASE_URL}${path}`;

export const AuthenticatedApp = () => {
  const [session, setSession] = useState<SessionState>({ status: "loading" });

  useEffect(() => {
    fetch(apiUrl("/api/auth/session"), { credentials: "include" })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Not authenticated");
        }
        return response.json() as Promise<{ username: string }>;
      })
      .then(({ username }) => setSession({ status: "authenticated", username }))
      .catch(() => setSession({ status: "unauthenticated" }));
  }, []);

  const handleLogin = async (username: string, password: string) => {
    const response = await fetch(apiUrl("/api/auth/login"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      throw new Error("Invalid username or password");
    }

    setSession({ status: "authenticated", username });
  };

  const handleLogout = async () => {
    await fetch(apiUrl("/api/auth/logout"), {
      method: "POST",
      credentials: "include",
    });
    setSession({ status: "unauthenticated" });
  };

  if (session.status === "loading") {
    return <LoadingState />;
  }

  if (session.status === "unauthenticated") {
    return <LoginForm onSubmit={handleLogin} />;
  }

  return <KanbanBoard username={session.username} onLogout={handleLogout} />;
};

const LoadingState = () => (
  <main className="flex min-h-screen items-center justify-center bg-[var(--surface)] px-6">
    <p className="text-sm font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
      Checking your workspace
    </p>
  </main>
);

const LoginForm = ({
  onSubmit,
}: {
  onSubmit: (username: string, password: string) => Promise<void>;
}) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await onSubmit(username, password);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Sign in failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[var(--surface)] px-6 py-12">
      <div className="pointer-events-none absolute -left-24 -top-24 h-80 w-80 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_transparent_70%)]" />
      <div className="pointer-events-none absolute -bottom-32 -right-20 h-96 w-96 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.2)_0%,_transparent_70%)]" />
      <form
        className="relative w-full max-w-md rounded-[32px] border border-[var(--stroke)] bg-white/90 p-8 shadow-[var(--shadow)] backdrop-blur"
        onSubmit={handleSubmit}
      >
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
          Single Board Kanban
        </p>
        <h1 className="mt-4 font-display text-4xl font-semibold text-[var(--navy-dark)]">
          Welcome back
        </h1>
        <p className="mt-3 text-sm leading-6 text-[var(--gray-text)]">
          Sign in to open your project workspace.
        </p>
        <div className="mt-8 space-y-5">
          <label className="block text-sm font-semibold text-[var(--navy-dark)]">
            Username
            <input
              className="mt-2 w-full rounded-2xl border border-[var(--stroke)] px-4 py-3 outline-none transition focus:border-[var(--primary-blue)]"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
          </label>
          <label className="block text-sm font-semibold text-[var(--navy-dark)]">
            Password
            <input
              className="mt-2 w-full rounded-2xl border border-[var(--stroke)] px-4 py-3 outline-none transition focus:border-[var(--primary-blue)]"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
        </div>
        {error ? (
          <p className="mt-4 text-sm font-semibold text-[var(--secondary-purple)]" role="alert">
            {error}
          </p>
        ) : null}
        <button
          className="mt-8 w-full rounded-2xl bg-[var(--secondary-purple)] px-5 py-3 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </main>
  );
};
