"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n";
import { AppShell } from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";
import type { ProjectSummary } from "@/lib/types";

export default function ProjectsListPage() {
  const { token, loading, user } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const [items, setItems] = useState<ProjectSummary[] | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/signin");
  }, [loading, user, router]);

  useEffect(() => {
    if (!token) return;
    api.listProjects(token).then(setItems).catch(() => setItems([]));
  }, [token]);

  if (loading || !user || !token) return null;

  const refresh = () => api.listProjects(token).then(setItems);
  const create = async () => {
    if (!newTitle.trim()) return;
    setBusy(true);
    try {
      const p = await api.createProject(token, { title: newTitle.trim() });
      router.push(`/projects/${p.id}`);
    } catch (e) {
      setBusy(false);
      alert(e instanceof ApiError ? e.message : String(e));
    }
  };

  return (
    <AppShell>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 16 }}>
        <div>
          <h2 className="ltx-section-title" style={{ margin: 0 }}>Projects</h2>
          <p className="ltx-section-subtitle">Long-form videos built scene by scene</p>
        </div>
        <button type="button" onClick={() => setShowNew((s) => !s)} className="ltx-primary">
          {showNew ? "cancel" : "new project"}
        </button>
      </div>

      {showNew && (
        <div className="ltx-card" style={{ marginBottom: 16, display: "flex", gap: 8 }}>
          <input
            className="ltx-field"
            placeholder="project title (e.g. 'Cat plays piano — 20s short')"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") create(); }}
            autoFocus
            style={{ flex: 1 }}
          />
          <button type="button" onClick={create} disabled={busy || !newTitle.trim()} className="ltx-primary">
            {busy ? "..." : "create"}
          </button>
        </div>
      )}

      {!items || items.length === 0 ? (
        <div className="ltx-card" style={{ textAlign: "center", padding: 48, color: "var(--ink-1)" }}>
          <p style={{ fontSize: 16, marginBottom: 8 }}>No projects yet.</p>
          <p style={{ fontSize: 13, color: "var(--ink-2)" }}>
            Create one and start composing scenes.
          </p>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
          {items.map((p) => (
            <Link
              key={p.id}
              href={`/projects/${p.id}`}
              style={{ textDecoration: "none", color: "inherit" }}
            >
              <div className="ltx-card" style={{ cursor: "pointer" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{p.title}</h3>
                  <span className="ltx-pill" data-status={p.status === "done" ? "succeeded" : p.status === "rendering" ? "running" : undefined}>
                    {p.status}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 16, fontSize: 13, color: "var(--ink-1)" }}>
                  <span>{p.scene_count} {p.scene_count === 1 ? "scene" : "scenes"}</span>
                  <span>·</span>
                  <span>{p.succeeded_count} done</span>
                </div>
                <div style={{ marginTop: 8, fontSize: 11, color: "var(--ink-2)" }}>
                  updated {p.updated_at?.slice(0, 16).replace("T", " ") ?? ""}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      <button type="button" onClick={refresh} className="ltx-secondary" style={{ marginTop: 16 }}>
        refresh
      </button>
    </AppShell>
  );
}