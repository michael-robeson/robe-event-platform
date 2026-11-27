import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { layoutTopology, type Topology, type TopologyNode } from "./topology-layout";
import "./style.css";

type Check = { status: string; kind?: string; name?: string; topic?: string; push_endpoint?: string };
type Status = { checked_at: string; services: Record<string, Check>; database: Check; emulator_resources: Record<string, Check> };
type ResourceGroup = { status: "available" | "unknown"; resources: { name: string; topic?: string }[]; error?: string };
type PubSubInventory = { topics: ResourceGroup; subscriptions: ResourceGroup };
type Observation = { consumer: string; event_id: string; event_type: string; contract_version: string; source: string; occurred_at: string; recorded_at: string };
type Page = { observations: Observation[]; sources: Record<string, string>; next_cursor: string | null };
type EventDetail = { event_id: string; sources: Record<string, { status: string; record: Record<string, unknown> | null }> };
type SyntheticTemplate = { id: string; name: string; origin: string; service: string };
type SyntheticTemplates = { templates: SyntheticTemplate[]; errors: string[] };
type Publication = { status: string; topic: string; message_id: string; event_id: string | null; correlation_id: string | null; causation_id: string | null };
type FlowNode = Node<{ label: React.ReactNode }>;
type FlowEdge = Edge<{
  label: string;
  description: string;
  points: { x: number; y: number }[];
  labelPosition: { x: number; y: number };
}, "message">;

function MessageEdge({ id, data, markerEnd }: EdgeProps<FlowEdge>) {
  if (!data) throw new Error(`Missing layout data for relationship ${id}`);
  const path = data.points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  return <>
    <BaseEdge id={id} path={path} markerEnd={markerEnd} />
    <EdgeLabelRenderer>
      <div className="topology-edge-label" title={data.description} aria-label={data.description} style={{
        transform: `translate(-50%, -50%) translate(${data.labelPosition.x}px, ${data.labelPosition.y}px)`,
      }}>{data.label}</div>
    </EdgeLabelRenderer>
  </>;
}

const edgeTypes = { message: MessageEdge };

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json() as Promise<T>;
}

function nodeEvidence(node: TopologyNode): string {
  if (node.declared && node.observed) return "Declared · observed";
  if (node.declared) return "Declared";
  return "Runtime discovered";
}

function TopologyView({ topology, onRefresh }: { topology: Topology | null; onRefresh: () => void }) {
  const [selectedId, setSelectedId] = useState("");
  const detailsRef = useRef<HTMLElement>(null);
  const selectedNode = topology?.nodes.find((node) => node.id === selectedId);
  const layout = useMemo(() => topology ? layoutTopology(topology) : null, [topology]);
  const declarations = layout?.hiddenDeclarations.filter((edge) =>
    edge.source === selectedId || edge.target === selectedId) ?? [];
  useEffect(() => { if (detailsRef.current) detailsRef.current.scrollTop = 0; }, [selectedId]);
  const graphNodes = useMemo<FlowNode[]>(() => (layout?.nodes ?? []).map(({ node, position }) => ({
      id: node.id,
      type: "default",
      position,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      className: `topology-node topology-node--${node.kind} topology-node--${node.status}`,
      data: {
        label: <button type="button" className="topology-node-content"
          aria-pressed={selectedId === node.id} aria-controls="topology-details"
          aria-label={`${node.name}, ${node.kind}, ${node.status.replaceAll("_", " ")}, ${nodeEvidence(node)}`}
          onClick={(event) => { event.stopPropagation(); setSelectedId(node.id); }}>
          <strong title={node.name}>{node.name}</strong>
          <span>{node.kind} · {node.status.replaceAll("_", " ")}</span>
          <small>{nodeEvidence(node)}</small>
        </button>,
      },
  })), [layout, selectedId]);
  const graphEdges = useMemo<FlowEdge[]>(() => (layout?.edges ?? []).map(({ edge, source, target, label, description, points, labelPosition }) => ({
    id: edge.id,
    source,
    target,
    type: "message",
    className: `topology-edge ${edge.evidence.includes("observed") ? "topology-edge--observed" : "topology-edge--declared"} topology-edge--${edge.status}`,
    markerEnd: { type: MarkerType.ArrowClosed, color: edge.status === "mismatch" ? "var(--edge-warning)" : edge.evidence.includes("observed") ? "var(--edge-observed)" : "var(--edge-declared)" },
    data: { label, description, points, labelPosition },
  })), [layout]);

  return <section className="topology-section" aria-labelledby="topology-heading">
    <div className="section-title">
      <div>
        <h2 id="topology-heading">Local service topology</h2>
        <p className="note">Edges: D = declared, O = observed. Arrows show message direction.</p>
      </div>
      <button onClick={onRefresh}>Refresh topology</button>
    </div>
    {topology && <p className="topology-timestamp">Checked {new Date(topology.checked_at).toLocaleString()}</p>}
    {layout && <div className="infrastructure-status" aria-label="Infrastructure status">
      {layout.infrastructure.map((node) => <button key={node.id} className="infrastructure-button"
        aria-pressed={selectedId === node.id} aria-controls="topology-details" onClick={() => setSelectedId(node.id)}>
        {node.name}: {node.status.replaceAll("_", " ")}
      </button>)}
    </div>}
    {topology && graphNodes.length === 0 && <p>No services or resources are currently declared or discovered.</p>}
    {topology && <div className="topology-layout">
      <div className="topology-canvas" aria-label="Interactive service topology graph">
        <ReactFlow
          key={JSON.stringify([graphNodes.map((node) => node.id), graphEdges.map((edge) => [edge.id, edge.data?.label])])}
          nodes={graphNodes}
          edges={graphEdges}
          edgeTypes={edgeTypes}
          onNodeClick={(_, node) => setSelectedId(node.id)}
          nodesDraggable={false}
          nodesConnectable={false}
          nodesFocusable={false}
          elementsSelectable={false}
          fitView
          fitViewOptions={{ padding: 0.08 }}
          minZoom={0.1}
          maxZoom={1.5}
        >
          <Background color="var(--graph-grid)" gap={24} />
          <Controls />
          <MiniMap pannable zoomable />
        </ReactFlow>
      </div>
      <aside id="topology-details" ref={detailsRef} className="topology-details"
        aria-label="Topology details" aria-live="polite" tabIndex={0}>
        {selectedNode ? <>
          <p className="eyebrow">{selectedNode.kind} · {selectedNode.status.replaceAll("_", " ")}</p>
          <h3>{selectedNode.name}</h3>
          <p className="evidence-label">{nodeEvidence(selectedNode)}</p>
          {declarations.length > 0 && <>
            <h4>Service declarations</h4>
            <ul>{declarations.map((edge) => {
              const service = topology.nodes.find((node) => node.id === edge.source);
              const topic = topology.nodes.find((node) => node.id === edge.target);
              const role = edge.relationship === "consumes" ? "consumption of" : "dead-letter topic";
              return <li key={edge.id}>{service?.name ?? edge.source} declares {role} {topic?.name ?? edge.target}
                {" "}({edge.evidence.join(" + ")}{edge.status === "available" ? "" : ` · ${edge.status.replaceAll("_", " ")}`})</li>;
            })}</ul>
          </>}
          <pre>{JSON.stringify(selectedNode.details, null, 2)}</pre>
        </> : <p>Select a node to inspect its identity, health, discovery evidence, or configuration.</p>}
      </aside>
    </div>}
    {selectedNode?.kind === "topic" && selectedNode.observed &&
      <SyntheticPublisher key={selectedNode.id} topic={selectedNode.id.slice("topic:".length)} />}
  </section>;
}

class SyntheticRequestError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

async function syntheticRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { cache: "no-store", ...init });
  const body: unknown = await response.json();
  if (!response.ok) {
    const detail = typeof body === "object" && body !== null && "detail" in body ? String(body.detail) : `Request failed (${response.status})`;
    throw new SyntheticRequestError(detail, response.status);
  }
  return body as T;
}

function SyntheticPublisher({ topic }: { topic: string }) {
  const [available, setAvailable] = useState<SyntheticTemplates | null>(null);
  const [choice, setChoice] = useState("");
  const [template, setTemplate] = useState<Record<string, unknown> | null>(null);
  const [payload, setPayload] = useState("");
  const [error, setError] = useState("");
  const [publication, setPublication] = useState<Publication | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [generation, setGeneration] = useState(0);
  const selected = choice === "" ? undefined : available?.templates[Number(choice)];

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ topic });
    syntheticRequest<SyntheticTemplates>(`/api/v1/synthetic/templates?${params}`, { signal: controller.signal })
      .then(setAvailable).catch((failure: unknown) => { if (!controller.signal.aborted) setError(String(failure)); });
    return () => controller.abort();
  }, [topic]);

  useEffect(() => {
    setTemplate(null);
    setPayload("");
    setPublication(null);
    setSubmitted(false);
    setError("");
    if (!selected) return;
    const controller = new AbortController();
    const params = new URLSearchParams({ topic, origin: selected.origin, template_id: selected.id });
    syntheticRequest<Record<string, unknown>>(`/api/v1/synthetic/template?${params}`, { signal: controller.signal })
      .then((message) => { setTemplate(message); setPayload(JSON.stringify(message.payload, null, 2)); })
      .catch((failure: unknown) => { if (!controller.signal.aborted) setError(String(failure)); });
    return () => controller.abort();
  }, [topic, selected, generation]);

  async function publish(event: React.FormEvent) {
    event.preventDefault();
    if (!selected || !template) return;
    let edited: unknown;
    try { edited = JSON.parse(payload) as unknown; }
    catch { setError("Payload must be valid JSON."); return; }
    setLoading(true);
    setSubmitted(true);
    setError("");
    try {
      const result = await syntheticRequest<Publication>("/api/v1/synthetic/publish", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Workbench-Intent": "synthetic-publication" },
        body: JSON.stringify({ topic, origin: selected.origin, template_id: selected.id, message: { ...template, payload: edited } }),
      });
      setPublication(result);
    } catch (failure) {
      if (failure instanceof SyntheticRequestError && failure.status === 422) {
        setSubmitted(false);
        setError(String(failure));
      } else {
        setError(`${String(failure)}. If broker acceptance is unknown, do not retry blindly.`);
      }
    } finally { setLoading(false); }
  }

  const envelope = template ? Object.fromEntries(Object.entries(template).filter(([key]) => key !== "payload")) : null;
  return <div className="synthetic-panel" aria-labelledby="synthetic-heading">
    <h3 id="synthetic-heading">Publish a synthetic message</h3>
    <p className="note">Local emulator only. Select a service-owned template, inspect or edit its payload, then explicitly publish once. Broker acceptance does not establish delivery or processing.</p>
    <p>Topic: <code>{topic}</code></p>
    {available?.errors.map((message) => <p role="status" key={message}>{message}</p>)}
    {available && available.templates.length === 0 && <p>No synthetic templates are available for this topic.</p>}
    {available && available.templates.length > 0 && <form onSubmit={(event) => void publish(event)}>
      <label htmlFor="synthetic-template">Service template</label>
      <select id="synthetic-template" value={choice} disabled={loading} onChange={(event) => setChoice(event.target.value)}>
        <option value="">Select a template</option>
        {available.templates.map((item, index) => <option value={index} key={`${item.origin}:${item.id}`}>{item.name} — {item.service}</option>)}
      </select>
      {template && <>
        <h4>Message envelope</h4>
        <pre>{JSON.stringify(envelope, null, 2)}</pre>
        <label htmlFor="synthetic-payload">Payload JSON</label>
        <textarea id="synthetic-payload" rows={10} value={payload} disabled={loading || submitted}
          onChange={(event) => setPayload(event.target.value)} spellCheck={false} />
        <div className="synthetic-actions">
          <button type="submit" disabled={loading || submitted}>Publish to local emulator</button>
          <button type="button" disabled={loading} onClick={() => setGeneration((value) => value + 1)}>Prepare new message</button>
        </div>
      </>}
    </form>}
    {error && <p role="alert">{error}</p>}
    {publication && <div role="status">
      <strong>Broker accepted the message.</strong>
      <p>Downstream delivery and processing have not been verified.</p>
      <pre>{JSON.stringify(publication, null, 2)}</pre>
    </div>}
  </div>;
}

function DiagnosticsView({
  status, statusError, inventory, inventoryError, page, detail, filter, eventId, listError,
  detailError, loading, onFilter, onLoadPage, onInspect, onEventId,
}: {
  status: Status | null;
  statusError: string;
  inventory: PubSubInventory | null;
  inventoryError: string;
  page: Page | null;
  detail: EventDetail | null;
  filter: string;
  eventId: string;
  listError: string;
  detailError: string;
  loading: boolean;
  onFilter: (filter: string) => void;
  onLoadPage: (filter: string, cursor?: string) => void;
  onInspect: (id: string) => void;
  onEventId: (id: string) => void;
}) {
  return <>
    <section aria-labelledby="status-heading">
      <div className="section-title"><h2 id="status-heading">Demonstration status</h2><span>{status && `Checked ${new Date(status.checked_at).toLocaleString()}`}</span></div>
      {statusError && <p role="alert">{statusError}</p>}
      {status && <div className="status-grid">
        {Object.entries(status.services).map(([name, check]) => <div className="status-card" key={name}><strong>{name}</strong><span>HTTP liveness: {check.status}</span></div>)}
        <div className="status-card"><strong>PostgreSQL</strong><span>Connection: {status.database.status}</span></div>
        {Object.entries(status.emulator_resources).map(([name, check]) => <div className="status-card" key={name}><strong>{name.replaceAll("_", " ")}</strong><span>Configuration: {check.status}</span>{check.name && <small>{check.name}</small>}{check.topic && <small>Topic: {check.topic}</small>}{check.push_endpoint && <small>Push: {check.push_endpoint}</small>}</div>)}
      </div>}
      <p className="note">Liveness does not verify database processing. Emulator checks only inspect resource configuration.</p>
    </section>
    <section aria-labelledby="pubsub-heading">
      <h2 id="pubsub-heading">Demonstration Pub/Sub inventory</h2>
      {inventoryError && <p role="alert">{inventoryError}</p>}
      {inventory && <>
        <div className="pubsub-grid">
          <div className="pubsub-group">
            <h3>Topics <span className="badge">{inventory.topics.status}</span></h3>
            {inventory.topics.status === "unknown" && <p className="resource-warning" role="status">{inventory.topics.error}; shown results may be incomplete.</p>}
            {inventory.topics.status === "available" && inventory.topics.resources.length === 0 && <p>No topics discovered.</p>}
            <ul className="resource-list">{inventory.topics.resources.map((topic) =>
              <li className="resource-item" key={topic.name}><code>{topic.name}</code></li>
            )}</ul>
          </div>
          <div className="pubsub-group">
            <h3>Subscriptions <span className="badge">{inventory.subscriptions.status}</span></h3>
            {inventory.subscriptions.status === "unknown" && <p className="resource-warning" role="status">{inventory.subscriptions.error}; shown results may be incomplete.</p>}
            {inventory.subscriptions.status === "available" && inventory.subscriptions.resources.length === 0 && <p>No subscriptions discovered.</p>}
            <ul className="resource-list">{inventory.subscriptions.resources.map((subscription) => {
              const resolved = inventory.topics.resources.some((topic) => topic.name === subscription.topic);
              return <li className="resource-item" key={subscription.name}>
                <code>{subscription.name}</code>
                <small>Topic: <code>{subscription.topic}</code>{resolved ? "" : " (unresolved in this inventory)"}</small>
              </li>;
            })}</ul>
          </div>
        </div>
        <p className="note">This is observed emulator configuration only; it does not establish publication, delivery, or consumer processing.</p>
      </>}
    </section>
    <div className="columns">
      <section aria-labelledby="observations-heading">
        <div className="section-title"><h2 id="observations-heading">Consumer observations</h2>
          <label>Consumer <select value={filter} onChange={(event) => onFilter(event.target.value)}><option value="all">All</option><option value="item">Item</option><option value="audit">Audit</option></select></label>
        </div>
        <p className="note">Best-effort database transaction-time sorting, not commit time, global event order, or a complete history. Refresh for new records.</p>
        {listError && <p role="alert">{listError}</p>}
        {page && <>
          <p>Sources: {Object.entries(page.sources).map(([name, value]) => `${name}: ${value}`).join(" · ")}</p>
          {page.observations.length === 0 && <p>No records observed in available sources.</p>}
          <ul className="observations">{page.observations.map((row) => <li key={`${row.consumer}-${row.event_id}`}>
            <button className="observation" onClick={() => onInspect(row.event_id)}>
              <span className="badge">{row.consumer}</span><strong>{row.event_type}</strong><code>{row.event_id}</code>
              <small>Source: {row.source} · Recorded: {row.recorded_at}</small>
            </button></li>)}</ul>
          {page.next_cursor && <button disabled={loading} onClick={() => onLoadPage(filter, page.next_cursor ?? undefined)}>Next page</button>}
        </>}
      </section>
      <section aria-labelledby="detail-heading">
        <h2 id="detail-heading">Event inspection</h2>
        <form onSubmit={(event) => { event.preventDefault(); onInspect(eventId); }}>
          <label htmlFor="event-id">Event UUID</label>
          <div className="search"><input id="event-id" value={eventId} onChange={(event) => onEventId(event.target.value)} required /><button>Inspect</button></div>
        </form>
        <p className="note">A missing record is not proof of failure; an unavailable source is unknown. A stored record does not prove broker acceptance or acknowledgment.</p>
        {detailError && <p role="alert">{detailError}</p>}
        {detail && <div>{Object.entries(detail.sources).map(([consumer, source]) => <article className="detail" key={consumer}>
          <h3>{consumer} <span className="badge">{source.status.replaceAll("_", " ")}</span></h3>
          {source.record && <pre>{JSON.stringify(source.record, null, 2)}</pre>}
        </article>)}</div>}
      </section>
    </div>
  </>;
}

function App() {
  const [topology, setTopology] = useState<Topology | null>(null);
  const [topologyError, setTopologyError] = useState("");
  const [tab, setTab] = useState<"topology" | "diagnostics">("topology");
  const [status, setStatus] = useState<Status | null>(null);
  const [inventory, setInventory] = useState<PubSubInventory | null>(null);
  const [page, setPage] = useState<Page | null>(null);
  const [detail, setDetail] = useState<EventDetail | null>(null);
  const [filter, setFilter] = useState("all");
  const [eventId, setEventId] = useState("");
  const [statusError, setStatusError] = useState("");
  const [inventoryError, setInventoryError] = useState("");
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [loading, setLoading] = useState(false);
  const diagnosticsLoaded = useRef(false);
  const listRequest = useRef(0);
  const detailRequest = useRef(0);
  const inventoryRequest = useRef(0);

  async function refreshTopology() {
    try { setTopology(await get<Topology>("/api/v1/topology")); setTopologyError(""); }
    catch (error) { setTopology(null); setTopologyError(String(error)); }
  }
  async function refreshStatus() {
    try { setStatus(await get<Status>("/api/v1/status")); setStatusError(""); }
    catch (error) { setStatus(null); setStatusError(String(error)); }
  }
  async function refreshInventory() {
    const request = ++inventoryRequest.current;
    try {
      const result = await get<PubSubInventory>("/api/v1/pubsub/resources");
      if (request === inventoryRequest.current) { setInventory(result); setInventoryError(""); }
    } catch (error) {
      if (request === inventoryRequest.current) { setInventory(null); setInventoryError(String(error)); }
    }
  }
  async function loadPage(selected: string, cursor?: string) {
    const request = ++listRequest.current;
    setLoading(true);
    try {
      const params = new URLSearchParams({ consumer: selected });
      if (cursor) params.set("cursor", cursor);
      const result = await get<Page>(`/api/v1/observations?${params}`);
      if (request !== listRequest.current) return;
      setPage(result);
      setListError("");
    } catch (error) { if (request === listRequest.current) { setPage(null); setListError(String(error)); } }
    finally { if (request === listRequest.current) setLoading(false); }
  }
  async function inspect(id: string) {
    const request = ++detailRequest.current;
    setEventId(id);
    setDetail(null);
    try {
      const result = await get<EventDetail>(`/api/v1/events/${encodeURIComponent(id)}`);
      if (request === detailRequest.current) { setDetail(result); setDetailError(""); }
    }
    catch (error) { if (request === detailRequest.current) { setDetail(null); setDetailError(String(error)); } }
  }
  function refreshDiagnostics() {
    diagnosticsLoaded.current = true;
    void refreshStatus();
    void refreshInventory();
    void loadPage(filter);
  }

  useEffect(() => { void refreshTopology(); }, []);
  useEffect(() => {
    if (tab === "diagnostics" && !diagnosticsLoaded.current) refreshDiagnostics();
  }, [tab]);

  return <main>
    <header>
      <div>
        <p className="eyebrow">LOCAL DEVELOPMENT</p>
        <h1>Event Platform Workbench</h1>
        <p>Explore service declarations, observed health, and live messaging topology.</p>
      </div>
      <button className={tab === "topology" ? "header-refresh--topology" : undefined} onClick={() => tab === "topology" ? void refreshTopology() : refreshDiagnostics()}>Refresh</button>
    </header>
    <nav className="workbench-tabs" aria-label="Workbench views">
      <button aria-pressed={tab === "topology"} onClick={() => setTab("topology")}>Service topology</button>
      <button aria-pressed={tab === "diagnostics"} onClick={() => setTab("diagnostics")}>Demonstration diagnostics</button>
    </nav>
    {tab === "topology" ? <>
      {topologyError && <p role="alert">{topologyError}</p>}
      <TopologyView topology={topology} onRefresh={() => void refreshTopology()} />
      <p className="note">A declared relationship is not proof of message activity. Health is an independent liveness observation.</p>
    </> : <DiagnosticsView
      status={status}
      statusError={statusError}
      inventory={inventory}
      inventoryError={inventoryError}
      page={page}
      detail={detail}
      filter={filter}
      eventId={eventId}
      listError={listError}
      detailError={detailError}
      loading={loading}
      onFilter={(value) => { setFilter(value); void loadPage(value); }}
      onLoadPage={(selected, cursor) => void loadPage(selected, cursor)}
      onInspect={(id) => void inspect(id)}
      onEventId={(id) => { setEventId(id); setDetail(null); detailRequest.current++; }}
    />}
  </main>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
