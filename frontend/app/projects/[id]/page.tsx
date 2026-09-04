"use client";
import { use, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { AppShell } from "@/components/AppShell";

// ---------- TimelineStrip component (Phase 2) ----------

function TimelineStrip({
  scenes, activeId, onSelect, apiBase, token, projectId, onConcatComplete,
}: {
  scenes: Scene[];
  activeId: string | null;
  onSelect: (id: string) => void;
  apiBase: string;
  token: string;
  projectId: string;
  onConcatComplete: () => void;
}) {
  const [concating, setConcating] = useState(false);
  const [finalPath, setFinalPath] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const succeeded = scenes.filter((s) => s.status === "succeeded");
  const canConcat = succeeded.length >= 2;

  const doConcat = async () => {
    if (!canConcat) return;
    setErr(null);
    setConcating(true);
    try {
      const r = await api.concatProject(token, projectId);
      setFinalPath(r.final_path);
      onConcatComplete();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally {
      setConcating(false);
    }
  };

  return (
    <div className="ltx-card" style={{ marginTop: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
          Timeline · {scenes.length} {scenes.length === 1 ? "scene" : "scenes"}
          {succeeded.length > 0 && (
            <span style={{ marginLeft: 8, fontSize: 12, color: "var(--ink-2)", fontWeight: 400 }}>
              ({succeeded.length} ready to concat)
            </span>
          )}
        </h3>
        <button
          type="button"
          onClick={doConcat}
          disabled={!canConcat || concating}
          className="ltx-primary"
          style={{ padding: "8px 16px", fontSize: 13 }}
          title={!canConcat ? "need at least 2 succeeded scenes" : ""}
        >
          {concating ? "concatenating…" : "concat all → final.mp4"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 8 }}>
        {scenes.map((s, i) => {
          const isActive = activeId === s.id;
          const hasVideo = s.status === "succeeded" && s.job_id;
          return (
            <div
              key={s.id}
              onClick={() => onSelect(s.id)}
              style={{
                flex: "0 0 160px",
                cursor: "pointer",
                border: isActive ? "2px solid var(--ink-0)" : "1px solid var(--line)",
                borderRadius: 6,
                background: "var(--bg-1)",
                overflow: "hidden",
                opacity: s.status === "succeeded" ? 1 : s.status === "running" || s.status === "queued" ? 0.7 : 0.4,
              }}
            >
              <div style={{ position: "relative", background: "#000", aspectRatio: "16/9" }}>
                {hasVideo ? (
                  <video
                    src={`${apiBase}/api/v1/jobs/${s.job_id}/result`}
                    muted
                    preload="metadata"
                    style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                  />
                ) : (
                  <div style={{
                    position: "absolute", inset: 0, display: "flex",
                    alignItems: "center", justifyContent: "center",
                    color: "var(--ink-2)", fontSize: 11,
                  }}>
                    {s.status === "running" || s.status === "queued" ? "⏳" : s.status === "failed" ? "✗" : "—"}
                  </div>
                )}
              </div>
              <div style={{ padding: "6px 8px", display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-2)" }}>{i + 1}</span>
                <span style={{
                  flex: 1, fontSize: 12, overflow: "hidden", textOverflow: "ellipsis",
                  whiteSpace: "nowrap", color: "var(--ink-0)",
                }}>
                  {s.prompt.slice(0, 18) || <em style={{ color: "var(--ink-2)" }}>—</em>}
                </span>
                <span
                  className="ltx-pill"
                  data-status={
                    s.status === "succeeded" ? "succeeded" :
                    s.status === "failed" ? "failed" :
                    s.status === "running" || s.status === "queued" ? "running" : undefined
                  }
                  style={{ fontSize: 9 }}
                >
                  {s.status === "running" || s.status === "queued" ? "..." : s.status}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {err && (
        <div className="ltx-pill" data-status="failed" style={{ display: "block", padding: "8px 12px", marginTop: 8 }}>
          {err}
        </div>
      )}

      {finalPath && (
        <div style={{ marginTop: 12 }}>
          <p className="ltx-section-subtitle" style={{ marginBottom: 8 }}>Final video</p>
          <video
            src={`${apiBase}/api/v1/files/${finalPath}`}
            controls
            style={{ width: "100%", maxWidth: 640, borderRadius: 8, background: "#000" }}
          />
          <p style={{ fontSize: 11, color: "var(--ink-2)", marginTop: 6 }}>
            <code>{finalPath}</code>
          </p>
        </div>
      )}
    </div>
  );
}
import { api, ApiError } from "@/lib/api";
import type { Project, Scene } from "@/lib/types";

const STYLE_OPTIONS = ["Cinematic", "Animated", "Realistic", "Dreamy"];
const DURATION_OPTIONS: Array<{ key: string; label: string; frames: number }> = [
  { key: "short", label: "short · ~5s", frames: 97 },
  { key: "medium", label: "medium · ~10s", frames: 161 },
  { key: "long", label: "long · ~20s", frames: 241 },
];

export default function ProjectEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { token, loading, user } = useAuth();
  const router = useRouter();

  const [project, setProject] = useState<Project | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/signin");
  }, [loading, user, router]);

  const refresh = async () => {
    if (!token) return;
    try {
      const p = await api.getProject(token, id);
      setProject(p);
      if (!activeId && p.scenes.length > 0) setActiveId(p.scenes[0].id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  };

  useEffect(() => { refresh(); /* eslint-disable-line */ }, [token, id]);

  // Poll scene job status when any scene is running/queued
  useEffect(() => {
    if (!token || !project) return;
    const hasActive = project.scenes.some(
      (s) => s.status === "running" || s.status === "queued"
    );
    if (!hasActive) return;
    const interval = setInterval(refresh, 2000);
    return () => clearInterval(interval);
    // eslint-disable-next-line
  }, [token, project?.scenes.map((s) => `${s.id}:${s.status}`).join(",")]);

  const active = useMemo(
    () => project?.scenes.find((s) => s.id === activeId) ?? null,
    [project, activeId]
  );

  if (loading || !user || !token) return null;
  if (!project) return <AppShell><p>loading…</p></AppShell>;

  const sceneBase = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:3381";

  const updateTitle = async (title: string) => {
    setBusy(true);
    try {
      const p = await api.patchProject(token!, id, { title });
      setProject(p);
    } finally {
      setBusy(false);
    }
  };

  const updateStyle = async (style: string) => {
    const p = await api.patchProject(token!, id, { style });
    setProject(p);
  };

  const addScene = async () => {
    const next = project.scenes.length;
    const s = await api.addScene(token!, id, { prompt: "", position: next });
    setProject({ ...project, scenes: [...project.scenes, s] });
    setActiveId(s.id);
  };

  const deleteScene = async (sceneId: string) => {
    if (!confirm("Delete this scene?")) return;
    await api.deleteScene(token!, id, sceneId);
    const scenes = project.scenes.filter((s) => s.id !== sceneId).map((s, i) => ({ ...s, position: i }));
    setProject({ ...project, scenes });
    if (activeId === sceneId) setActiveId(scenes[0]?.id ?? null);
  };

  const updateScene = async (sceneId: string, body: Partial<Scene>) => {
    const s = await api.patchScene(token!, id, sceneId, body);
    setProject({
      ...project,
      scenes: project.scenes.map((x) => (x.id === sceneId ? s : x)),
    });
  };

  const generate = async (sceneId: string) => {
    setError(null);
    try {
      const s = await api.generateScene(token!, id, sceneId);
      setProject({
        ...project,
        scenes: project.scenes.map((x) => (x.id === sceneId ? s : x)),
      });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  };

  const generateAll = async () => {
    setError(null);
    setBusy(true);
    try {
      for (const s of project.scenes) {
        if (s.status === "draft" || s.status === "failed") {
          await generate(s.id);
        }
      }
    } finally {
      setBusy(false);
    }
  };

  const moveScene = async (sceneId: string, direction: -1 | 1) => {
    const sorted = [...project.scenes].sort((a, b) => a.position - b.position);
    const idx = sorted.findIndex((s) => s.id === sceneId);
    const target = idx + direction;
    if (target < 0 || target >= sorted.length) return;
    [sorted[idx], sorted[target]] = [sorted[target], sorted[idx]];
    const new_ids = sorted.map((s) => s.id);
    const updated = await api.reorderScenes(token!, id, new_ids);
    setProject(updated);
  };

  const deleteProject = async () => {
    if (!confirm(`Delete project "${project.title}" and all scenes?`)) return;
    await api.deleteProject(token!, id);
    router.push("/projects");
  };

  const sortedScenes = [...project.scenes].sort((a, b) => a.position - b.position);

  return (
    <AppShell>
      {/* Top bar: title + style + actions */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24, gap: 16, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 240 }}>
          <input
            className="ltx-field"
            value={project.title}
            onChange={(e) => setProject({ ...project, title: e.target.value })}
            onBlur={(e) => updateTitle(e.target.value)}
            style={{ fontSize: 18, fontWeight: 600, padding: "8px 12px" }}
          />
          <div style={{ marginTop: 4, fontSize: 12, color: "var(--ink-2)" }}>
            {project.scenes.length} {project.scenes.length === 1 ? "scene" : "scenes"} · {sortedScenes.filter((s) => s.status === "succeeded").length} done · model: <code>{project.model_id}</code>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <select
            className="ltx-field"
            value={project.style}
            onChange={(e) => updateStyle(e.target.value)}
            style={{ width: "auto" }}
          >
            {STYLE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button type="button" onClick={generateAll} disabled={busy} className="ltx-primary">
            {busy ? "generating..." : "generate all"}
          </button>
          <button type="button" onClick={deleteProject} className="ltx-secondary" style={{ color: "#c66" }}>
            delete project
          </button>
        </div>
      </div>

      {error && (
        <div className="ltx-pill" data-status="failed" style={{ display: "block", padding: "8px 12px", marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* 3-pane editor */}
      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr 1fr", gap: 16 }}>
        {/* LEFT: scene list */}
        <div className="ltx-card" style={{ padding: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>Scenes</h3>
            <button type="button" onClick={addScene} className="ltx-secondary" style={{ padding: "4px 10px", fontSize: 12 }}>
              + add
            </button>
          </div>
          <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 4 }}>
            {sortedScenes.map((s, i) => (
              <li
                key={s.id}
                onClick={() => setActiveId(s.id)}
                style={{
                  cursor: "pointer",
                  padding: "8px 10px",
                  borderRadius: 6,
                  background: activeId === s.id ? "var(--ink-0)" : "transparent",
                  color: activeId === s.id ? "var(--bg-0)" : "var(--ink-0)",
                  fontSize: 13,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <span style={{
                  width: 18, height: 18, borderRadius: "50%",
                  background: "var(--bg-2)", color: "var(--ink-0)",
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  fontSize: 11, fontWeight: 600,
                }}>{i + 1}</span>
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {s.prompt.slice(0, 24) || <em style={{ color: "var(--ink-2)" }}>no prompt</em>}
                </span>
                <span className="ltx-pill" data-status={s.status === "succeeded" ? "succeeded" : s.status === "failed" ? "failed" : s.status === "running" || s.status === "queued" ? "running" : undefined} style={{ fontSize: 10 }}>
                  {s.status === "running" || s.status === "queued" ? "..." : s.status}
                </span>
              </li>
            ))}
          </ol>
        </div>

        {/* CENTER: editor */}
        <div className="ltx-card">
          {active ? (
            <>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
                  Scene {sortedScenes.findIndex((s) => s.id === active.id) + 1}
                </h3>
                <div style={{ display: "flex", gap: 4 }}>
                  <button type="button" onClick={() => moveScene(active.id, -1)} className="ltx-secondary" style={{ padding: "4px 10px", fontSize: 12 }}>↑</button>
                  <button type="button" onClick={() => moveScene(active.id, +1)} className="ltx-secondary" style={{ padding: "4px 10px", fontSize: 12 }}>↓</button>
                  <button type="button" onClick={() => deleteScene(active.id)} className="ltx-secondary" style={{ padding: "4px 10px", fontSize: 12, color: "#c66" }}>delete</button>
                </div>
              </div>

              <label className="ltx-label">Prompt</label>
              <textarea
                className="ltx-input"
                value={active.prompt}
                onChange={(e) => setProject({
                  ...project,
                  scenes: project.scenes.map((s) => s.id === active.id ? { ...s, prompt: e.target.value } : s),
                })}
                onBlur={(e) => updateScene(active.id, { prompt: e.target.value })}
                placeholder="describe this scene (the model will prepend the project style)"
                rows={4}
                style={{ minHeight: 100, marginBottom: 12 }}
              />

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12 }}>
                <div>
                  <label className="ltx-label">Length</label>
                  <select
                    className="ltx-field"
                    value={active.duration}
                    onChange={(e) => updateScene(active.id, { duration: e.target.value })}
                  >
                    {DURATION_OPTIONS.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="ltx-label">Quality</label>
                  <select
                    className="ltx-field"
                    value={active.quality}
                    onChange={(e) => updateScene(active.id, { quality: e.target.value })}
                  >
                    <option value="draft">draft · fast</option>
                    <option value="standard">standard</option>
                    <option value="high">high · slow</option>
                  </select>
                </div>
              </div>

              <div style={{ marginBottom: 12 }}>
                <label className="ltx-label">Status</label>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="ltx-pill" data-status={active.status === "succeeded" ? "succeeded" : active.status === "failed" ? "failed" : "running"}>
                    {active.status}
                  </span>
                  {active.error && <span style={{ fontSize: 12, color: "#c66" }}>{active.error}</span>}
                </div>
              </div>

              <button
                type="button"
                onClick={() => generate(active.id)}
                disabled={!active.prompt.trim()}
                className="ltx-primary"
                style={{ width: "100%" }}
              >
                generate this scene
              </button>
            </>
          ) : (
            <p style={{ color: "var(--ink-1)", fontSize: 13 }}>No scene selected. Add one to start.</p>
          )}
        </div>

        {/* RIGHT: preview */}
        <div className="ltx-card">
          <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>Preview</h3>
          {active?.status === "succeeded" && active.job_id ? (
            <div>
              <video
                src={`${sceneBase}/api/v1/jobs/${active.job_id}/result`}
                controls
                style={{ width: "100%", borderRadius: 8, background: "#000" }}
              />
              <p style={{ fontSize: 11, color: "var(--ink-2)", marginTop: 8 }}>
                job: <code>{active.job_id}</code>
              </p>
            </div>
          ) : (
            <div style={{ background: "#000", borderRadius: 8, aspectRatio: "16/9", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--ink-2)" }}>
              {active?.status === "running" || active?.status === "queued" ? "generating…" : "no preview yet"}
            </div>
          )}
        </div>
      </div>

      {/* TIMELINE (Phase 2) */}
      <TimelineStrip
        scenes={sortedScenes}
        activeId={activeId}
        onSelect={setActiveId}
        apiBase={sceneBase}
        token={token!}
        projectId={id}
        onConcatComplete={refresh}
      />

      <p style={{ marginTop: 24, fontSize: 12, color: "var(--ink-2)" }}>
        Note: scenes chain by last-frame → first-frame, so the order matters. Generate sequentially for coherent visual flow.
      </p>
    </AppShell>
  );
}