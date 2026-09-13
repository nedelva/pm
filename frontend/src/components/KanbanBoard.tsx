"use client";

import { useEffect, useMemo, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { AIChatSidebar } from "@/components/AIChatSidebar";
import {
  createCard,
  deleteCard,
  editCard,
  getBoard,
  moveCard as persistMoveCard,
  renameColumn,
} from "@/lib/api";
import { createId, initialData, moveCard as moveCardLocally, type BoardData } from "@/lib/kanban";

export const KanbanBoard = ({
  username,
  onLogout,
}: {
  username?: string;
  onLogout?: () => void | Promise<void>;
}) => {
  const isPersistent = Boolean(username && onLogout);
  const [board, setBoard] = useState<BoardData | null>(() =>
    isPersistent ? null : initialData
  );
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadBoard = () => {
    setError(null);
    getBoard()
      .then(setBoard)
      .catch((loadError: unknown) => {
        setError(loadError instanceof Error ? loadError.message : "Unable to load the board.");
      });
  };

  useEffect(() => {
    if (!isPersistent) return;
    getBoard()
      .then(setBoard)
      .catch((loadError: unknown) => {
        setError(loadError instanceof Error ? loadError.message : "Unable to load the board.");
      });
  }, [isPersistent]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const cardsById = useMemo(() => board?.cards ?? {}, [board]);

  const applyMutation = async (mutation: () => Promise<BoardData>) => {
    setError(null);
    try {
      setBoard(await mutation());
    } catch (mutationError) {
      setError(
        mutationError instanceof Error
          ? mutationError.message
          : "Unable to save the board change."
      );
    }
  };

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!over || active.id === over.id) {
      return;
    }

    if (!board) return;
    const nextColumns = moveCardLocally(board.columns, active.id as string, over.id as string);
    const targetColumn = nextColumns.find((column) =>
      column.cardIds.includes(active.id as string)
    );
    if (!targetColumn) return;
    const position = targetColumn.cardIds.indexOf(active.id as string);

    if (!isPersistent) {
      setBoard({ ...board, columns: nextColumns });
      return;
    }
    void applyMutation(() =>
      persistMoveCard(active.id as string, targetColumn.id, position)
    );
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    if (!board) return;
    if (!isPersistent) {
      setBoard({
        ...board,
        columns: board.columns.map((column) =>
          column.id === columnId ? { ...column, title } : column
        ),
      });
      return;
    }
    void applyMutation(() => renameColumn(columnId, title));
  };

  const handleAddCard = (columnId: string, title: string, details: string) => {
    if (!board) return;
    if (isPersistent) {
      void applyMutation(() => createCard(columnId, title, details || "No details yet."));
      return;
    }
    const id = createId("card");
    setBoard({
      ...board,
      cards: {
        ...board.cards,
        [id]: { id, title, details: details || "No details yet." },
      },
      columns: board.columns.map((column) =>
        column.id === columnId
          ? { ...column, cardIds: [...column.cardIds, id] }
          : column
      ),
    });
  };

  const handleDeleteCard = (columnId: string, cardId: string) => {
    if (!board) return;
    if (isPersistent) {
      void applyMutation(() => deleteCard(cardId));
      return;
    }
    setBoard({
      ...board,
      cards: Object.fromEntries(
        Object.entries(board.cards).filter(([id]) => id !== cardId)
      ),
      columns: board.columns.map((column) =>
        column.id === columnId
          ? { ...column, cardIds: column.cardIds.filter((id) => id !== cardId) }
          : column
      ),
    });
  };

  const handleEditCard = (cardId: string, title: string, details: string) => {
    if (!board) return;
    if (isPersistent) {
      void applyMutation(() => editCard(cardId, title, details));
      return;
    }
    setBoard({
      ...board,
      cards: { ...board.cards, [cardId]: { id: cardId, title, details } },
    });
  };

  const activeCard = activeCardId && board ? cardsById[activeCardId] : null;

  if (!board) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--surface)] px-6">
        <div className="text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
            {error ?? "Loading your board"}
          </p>
          {error ? (
            <button
              className="mt-5 rounded-2xl bg-[var(--secondary-purple)] px-4 py-3 text-sm font-semibold text-white"
              type="button"
              onClick={loadBoard}
            >
              Try again
            </button>
          ) : null}
        </div>
      </main>
    );
  }

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1600px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="flex items-start gap-4">
              <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                  {username ? `Signed in as ${username}` : "Focus"}
                </p>
                <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                  One board. Five columns. Zero clutter.
                </p>
              </div>
              {onLogout ? (
                <button
                  className="rounded-2xl border border-[var(--stroke)] px-4 py-3 text-sm font-semibold text-[var(--navy-dark)] transition hover:border-[var(--secondary-purple)]"
                  type="button"
                  onClick={onLogout}
                >
                  Log out
                </button>
              ) : null}
            </div>
          </div>
          {error ? (
            <p className="text-sm font-semibold text-[var(--secondary-purple)]" role="alert">
              {error}
            </p>
          ) : null}
          <div className="flex flex-wrap items-center gap-4">
            {board.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
          </div>
        </header>

        <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <section className="grid gap-6 lg:grid-cols-5">
              {board.columns.map((column) => (
                <KanbanColumn
                  key={column.id}
                  column={column}
                  cards={column.cardIds.map((cardId) => board.cards[cardId])}
                  onRename={handleRenameColumn}
                  onAddCard={handleAddCard}
                  onDeleteCard={handleDeleteCard}
                  onEditCard={handleEditCard}
                />
              ))}
            </section>
            <DragOverlay>
              {activeCard ? (
                <div className="w-[260px]">
                  <KanbanCardPreview card={activeCard} />
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>
          {isPersistent ? <AIChatSidebar onBoardUpdate={setBoard} /> : null}
        </div>
      </main>
    </div>
  );
};
