import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type Check = { status: string; kind?: string; name?: string; topic?: string; push_endpoint?: string };
type Status = { checked_at: string; services: Record<string, Check>; database: Check; emulator_resources: Record<string, Check> };
type Observation = { consumer: string; event_id: string; event_type: string; contract_version: string; source: string; occurred_at: string; recorded_at: string };
type Page = { observations: Observation[]; sources: Record<string, string>; next_cursor: string | null };
type EventDetail = { event_id: string; sources: Record<string, { status: string; record: Record<string, unknown> | null }> };

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json() as Promise<T>;
}

function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [page, setPage] = useState<Page | null>(null);
  const [detail, setDetail] = useState<EventDetail | null>(null);
  const [filter, setFilter] = useState("all");
  const [eventId, setEventId] = useState("");
  const [statusError, setStatusError] = useState("");
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [loading, setLoading] = useState(false);
  const listRequest = useRef(0);
  const detailRequest = useRef(0);

  async function refreshStatus() {
    try { setStatus(await get<Status>("/api/v1/status")); setStatusError(""); }
    catch (error) { setStatus(null); setStatusError(String(error)); }
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
  useEffect(() => { void refreshStatus(); void loadPage("all"); }, []);

  return <main>
    <header>
      <div><p className="eyebrow">LOCAL DEVELOPMENT / READ ONLY</p><h1>Event Platform Workbench</h1>
      <p>Inspect independently persisted consumer records—not a publication or delivery history.</p></div>
      <button onClick={() => { void refreshStatus(); void loadPage(filter); }}>Refresh</button>
    </header>
    <section aria-labelledby="status-heading">
      <div className="section-title"><h2 id="status-heading">Local status</h2><span>{status && `Checked ${new Date(status.checked_at).toLocaleString()}`}</span></div>
      {statusError && <p role="alert">{statusError}</p>}
      {status && <div className="status-grid">
        {Object.entries(status.services).map(([name, check]) => <div className="status-card" key={name}><strong>{name}</strong><span>HTTP liveness: {check.status}</span></div>)}
        <div className="status-card"><strong>PostgreSQL</strong><span>Connection: {status.database.status}</span></div>
        {Object.entries(status.emulator_resources).map(([name, check]) => <div className="status-card" key={name}><strong>{name.replaceAll("_", " ")}</strong><span>Configuration: {check.status}</span>{check.name && <small>{check.name}</small>}{check.topic && <small>Topic: {check.topic}</small>}{check.push_endpoint && <small>Push: {check.push_endpoint}</small>}</div>)}
      </div>}
      <p className="note">Liveness does not verify database processing. Emulator checks only inspect resource configuration.</p>
    </section>
    <div className="columns">
      <section aria-labelledby="observations-heading">
        <div className="section-title"><h2 id="observations-heading">Consumer observations</h2>
          <label>Consumer <select value={filter} onChange={(e) => { setFilter(e.target.value); void loadPage(e.target.value); }}><option value="all">All</option><option value="item">Item</option><option value="audit">Audit</option></select></label>
        </div>
        <p className="note">Best-effort database transaction-time sorting, not commit time, global event order, or a complete history. Refresh for new records.</p>
        {listError && <p role="alert">{listError}</p>}
        {page && <>
          <p>Sources: {Object.entries(page.sources).map(([name, value]) => `${name}: ${value}`).join(" · ")}</p>
          {page.observations.length === 0 && <p>No records observed in available sources.</p>}
          <ul className="observations">{page.observations.map((row) => <li key={`${row.consumer}-${row.event_id}`}>
            <button className="observation" onClick={() => void inspect(row.event_id)}>
              <span className="badge">{row.consumer}</span><strong>{row.event_type}</strong><code>{row.event_id}</code>
              <small>Source: {row.source} · Recorded: {row.recorded_at}</small>
            </button></li>)}</ul>
          {page.next_cursor && <button disabled={loading} onClick={() => void loadPage(filter, page.next_cursor ?? undefined)}>Next page</button>}
        </>}
      </section>
      <section aria-labelledby="detail-heading">
        <h2 id="detail-heading">Event inspection</h2>
        <form onSubmit={(event) => { event.preventDefault(); void inspect(eventId); }}>
          <label htmlFor="event-id">Event UUID</label>
          <div className="search"><input id="event-id" value={eventId} onChange={(event) => { setEventId(event.target.value); setDetail(null); detailRequest.current++; }} required /><button>Inspect</button></div>
        </form>
        <p className="note">A missing record is not proof of failure; an unavailable source is unknown. A stored record does not prove broker acceptance or acknowledgment.</p>
        {detailError && <p role="alert">{detailError}</p>}
        {detail && <div>{Object.entries(detail.sources).map(([consumer, source]) => <article className="detail" key={consumer}>
          <h3>{consumer} <span className="badge">{source.status.replaceAll("_", " ")}</span></h3>
          {source.record && <pre>{JSON.stringify(source.record, null, 2)}</pre>}
        </article>)}</div>}
      </section>
    </div>
  </main>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
