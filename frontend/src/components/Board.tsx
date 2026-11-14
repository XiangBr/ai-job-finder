import {
  closestCorners, DndContext, DragOverlay, PointerSensor, pointerWithin, TouchSensor, useDroppable, useSensor, useSensors,
  type CollisionDetection, type DragEndEvent, type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useEffect, useState } from "react";
import { api, COLUNAS, type Board as BoardT, type CardData, type Coluna } from "../api";
import { Badge, TagBadge, useToast } from "./ui";

type Cols = Record<Coluna, CardData[]>;

// Prefere o que está sob o ponteiro (card ou coluna); se nada, o mais próximo.
const collision: CollisionDetection = (args) => {
  const hits = pointerWithin(args);
  if (hits.length) {
    const card = hits.find((h) => !String(h.id).startsWith("col:"));
    return card ? [card] : hits;
  }
  return closestCorners(args);
};

export default function Board({ board, onOpen, onChange }: { board: BoardT; onOpen: (id: number) => void; onChange: () => void }) {
  const [cols, setCols] = useState<Cols>(board.colunas);
  const [active, setActive] = useState<CardData | null>(null);
  const [showDesc, setShowDesc] = useState(false);
  const [busca, setBusca] = useState("");
  const toast = useToast();
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 6 } }),
  );

  useEffect(() => {
    if (!active) setCols(board.colunas);
  }, [board, active]);

  const findCol = (cardId: number): Coluna | undefined =>
    (Object.keys(cols) as Coluna[]).find((c) => cols[c].some((x) => x.card_id === cardId));

  function onDragStart(e: DragStartEvent) {
    const col = findCol(Number(e.active.id));
    setActive(col ? cols[col].find((x) => x.card_id === Number(e.active.id)) ?? null : null);
  }

  async function onDragEnd(e: DragEndEvent) {
    setActive(null);
    const { active: a, over } = e;
    if (!over) return;
    const cardId = Number(a.id);
    const from = findCol(cardId);
    const overId = String(over.id);
    const to: Coluna | undefined = overId.startsWith("col:") ? (overId.slice(4) as Coluna) : findCol(Number(overId));
    if (!from || !to) return;

    const card = cols[from].find((x) => x.card_id === cardId)!;
    const target = cols[to].filter((x) => x.card_id !== cardId);
    let idx = overId.startsWith("col:") ? target.length : target.findIndex((x) => x.card_id === Number(overId));
    if (idx < 0) idx = target.length;
    if (from === to && cols[from].findIndex((x) => x.card_id === cardId) === idx) return;

    const prev = target[idx - 1]?.posicao;
    const next = target[idx]?.posicao;
    const posicao = prev == null && next == null ? 0 : prev == null ? next! - 1 : next == null ? prev + 1 : (prev + next) / 2;

    const moved = { ...card, coluna: to, posicao };
    const newTarget = [...target.slice(0, idx), moved, ...target.slice(idx)];
    setCols({ ...cols, [from]: cols[from].filter((x) => x.card_id !== cardId), [to]: newTarget });
    try {
      await api(`/cards/${cardId}`, { method: "PATCH", body: { coluna: to, posicao } });
      if (from !== to) toast(`${card.cargo} → ${COLUNAS.find((c) => c.id === to)?.titulo}`);
      onChange();
    } catch (err) {
      toast((err as Error).message, "erro");
      setCols(board.colunas);
    }
  }

  const q = busca.trim().toLowerCase();
  const filt = (list: CardData[]) => (q ? list.filter((c) => `${c.cargo} ${c.empresa} ${c.local}`.toLowerCase().includes(q)) : list);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 px-4 pt-3 sm:px-6">
        <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Filtrar por cargo, empresa ou local"
          className="w-full max-w-xs rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-indigo-400" />
        {!board.agenda.ativo && <Badge tone="amber">busca automática pausada</Badge>}
      </div>
      <DndContext sensors={sensors} collisionDetection={collision} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setActive(null)}>
        <div className="flex min-h-0 flex-1 gap-3 overflow-x-auto px-4 py-3 sm:px-6">
          {COLUNAS.map((c) =>
            c.id === "descartadas" && !showDesc ? (
              <CollapsedColumn key={c.id} count={cols.descartadas.length} onClick={() => setShowDesc(true)} />
            ) : (
              <Column key={c.id} id={c.id} titulo={c.titulo} cor={c.cor} cards={filt(cols[c.id] ?? [])}
                onOpen={onOpen} onCollapse={c.id === "descartadas" ? () => setShowDesc(false) : undefined} />
            ),
          )}
        </div>
        <DragOverlay>{active ? <CardView card={active} dragging /> : null}</DragOverlay>
      </DndContext>
    </div>
  );
}

function Column({ id, titulo, cor, cards, onOpen, onCollapse }: {
  id: Coluna; titulo: string; cor: string; cards: CardData[]; onOpen: (id: number) => void; onCollapse?: () => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: `col:${id}` });
  return (
    <section className={`flex w-72 shrink-0 flex-col rounded-2xl bg-slate-100/80 ${isOver ? "ring-2 ring-indigo-300" : ""}`}>
      <header className="flex items-center gap-2 px-4 pb-2 pt-4">
        <span className={`h-2 w-2 rounded-full ${cor}`} />
        <h2 className="text-sm font-semibold text-slate-800">{titulo}</h2>
        <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-600">{cards.length}</span>
        {onCollapse && <button onClick={onCollapse} className="ml-auto text-xs text-slate-400 hover:text-slate-700">recolher</button>}
      </header>
      <div ref={setNodeRef} className="flex min-h-24 flex-1 flex-col gap-2 overflow-y-auto px-3 pb-3">
        <SortableContext items={cards.map((c) => c.card_id)} strategy={verticalListSortingStrategy}>
          {cards.map((c) => <SortableCard key={c.card_id} card={c} onOpen={onOpen} />)}
        </SortableContext>
        {cards.length === 0 && <p className="px-1 pt-2 text-xs text-slate-400">Nenhuma vaga aqui</p>}
      </div>
    </section>
  );
}

function CollapsedColumn({ count, onClick }: { count: number; onClick: () => void }) {
  const { setNodeRef, isOver } = useDroppable({ id: "col:descartadas" });
  return (
    <button ref={setNodeRef} onClick={onClick} title="Mostrar descartadas"
      className={`flex w-12 shrink-0 flex-col items-center gap-2 rounded-2xl bg-slate-100/80 pt-4 text-slate-500 hover:bg-slate-200/70 ${isOver ? "ring-2 ring-indigo-300" : ""}`}>
      <span className="h-2 w-2 rounded-full bg-slate-400" />
      <span className="rounded-full bg-slate-200 px-1.5 py-0.5 text-xs">{count}</span>
      <span className="text-xs font-medium [writing-mode:vertical-rl]">Descartadas</span>
    </button>
  );
}

function SortableCard({ card, onOpen }: { card: CardData; onOpen: (id: number) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: card.card_id });
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }} {...attributes} {...listeners}
      className={isDragging ? "opacity-40" : ""} onClick={() => onOpen(card.id)}>
      <CardView card={card} />
    </div>
  );
}

function CardView({ card, dragging }: { card: CardData; dragging?: boolean }) {
  const local = [card.empresa, card.modelo === "remoto" ? "Remoto" : card.local.replace(/, Brazil$/, "")].filter(Boolean).join(" · ");
  return (
    <article className={`cursor-pointer rounded-xl border border-slate-200 bg-white px-3.5 py-3 shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition hover:border-slate-300 ${dragging ? "rotate-2 shadow-lg" : ""}`}>
      <h3 className="text-sm font-semibold leading-snug text-slate-900">{card.cargo}</h3>
      <p className="mt-0.5 truncate text-xs text-slate-500">{local}</p>
      {(card.tag || card.alertas.length > 0 || card.prazo || card.tem_notas || (card.coluna === "descartadas" && card.motivo_descarte)) && (
        <div className="mt-2 flex flex-wrap gap-1">
          <TagBadge tag={card.tag} score={card.score} />
          {card.alertas.length > 0 && <Badge tone="amber" title={card.alertas.join("\n")}>alerta</Badge>}
          {card.prazo && <Badge tone="amber">prazo: {card.prazo}</Badge>}
          {card.coluna === "aprovado" && <Badge tone="green">🎉 Aprovada!</Badge>}
          {card.tem_notas && <Badge>notas</Badge>}
          {card.coluna === "descartadas" && card.motivo_descarte && (
            <span className="text-[11px] leading-tight text-slate-400">{card.motivo_descarte}</span>
          )}
        </div>
      )}
    </article>
  );
}
