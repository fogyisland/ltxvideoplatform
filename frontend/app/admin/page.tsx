"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n";
import { AppShell } from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";
import type { AdminModel, AdminStats, AdminUser } from "@/lib/types";

type Tab = "users" | "models" | "stats";

export default function AdminPage() {
  const { token, loading, user } = useAuth();
  const { t } = useI18n();
  const router = useRouter();

  const [tab, setTab] = useState<Tab>("users");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [models, setModels] = useState<AdminModel[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);

  const [newUser, setNewUser] = useState({ username: "", email: "", password: "", role: "user" });
  const [targetId, setTargetId] = useState("");
  const [newPw, setNewPw] = useState("");
  const [targetModelId, setTargetModelId] = useState("");
  const [downloadStatus, setDownloadStatus] = useState<string>("");
  const [feedback, setFeedback] = useState<string>("");

  useEffect(() => {
    if (!loading) {
      if (!user) router.replace("/signin");
      else if (user.role !== "admin") router.replace("/create");
    }
  }, [loading, user, router]);

  useEffect(() => {
    if (!token || user?.role !== "admin") return;
    api.adminListUsers(token).then(setUsers).catch(() => setUsers([]));
    api.adminListModels(token).then(setModels).catch(() => setModels([]));
    api.adminStats(token).then(setStats).catch(() => setStats(null));
  }, [token, user]);

  if (loading || !user || !token) return null;
  if (user.role !== "admin") return null;

  const refreshUsers = () => api.adminListUsers(token!).then(setUsers);
  const refreshModels = () => api.adminListModels(token!).then(setModels);

  const addUser = async () => {
    setFeedback("");
    try {
      await api.adminCreateUser(token!, {
        username: newUser.username, password: newUser.password, role: newUser.role as "user" | "admin",
        email: newUser.email || null,
      });
      setFeedback("✓ added");
      setNewUser({ username: "", email: "", password: "", role: "user" });
      await refreshUsers();
    } catch (e) {
      setFeedback(e instanceof ApiError ? `✗ ${e.message}` : `✗ ${e}`);
    }
  };

  const resetPw = async () => {
    if (!targetId || !newPw) return;
    setFeedback("");
    try {
      await api.adminResetPassword(token!, Number(targetId), newPw);
      setFeedback("✓ password reset");
      setNewPw("");
    } catch (e) {
      setFeedback(e instanceof ApiError ? `✗ ${e.message}` : `✗ ${e}`);
    }
  };

  const toggleActive = async (u: AdminUser) => {
    try {
      await api.adminPatchUser(token!, u.id, { is_active: !u.is_active });
      await refreshUsers();
    } catch (e) {
      setFeedback(e instanceof ApiError ? `✗ ${e.message}` : `✗ ${e}`);
    }
  };

  const downloadModel = async () => {
    if (!targetModelId) return;
    setDownloadStatus("starting…");
    try {
      const r = await api.adminDownloadModel(token!, targetModelId);
      setDownloadStatus(`status: ${r.status}`);
    } catch (e) {
      setDownloadStatus(e instanceof ApiError ? `✗ ${e.message}` : `✗ ${e}`);
    }
  };

  const tabBtn = (k: Tab) => ({
    padding: "8px 14px",
    background: tab === k ? "var(--ink-0)" : "transparent",
    color: tab === k ? "var(--bg-0)" : "var(--ink-1)",
    border: "1px solid var(--line)",
    borderRadius: 999,
    cursor: "pointer",
    fontWeight: 500,
  });

  return (
    <AppShell>
      <h2 className="ltx-section-title" style={{ marginTop: 0 }}>{t("nav_admin")}</h2>

      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <button type="button" onClick={() => setTab("users")} style={tabBtn("users")}>
          {t("admin_users")}
        </button>
        <button type="button" onClick={() => setTab("models")} style={tabBtn("models")}>
          {t("admin_models")}
        </button>
        <button type="button" onClick={() => setTab("stats")} style={tabBtn("stats")}>
          {t("admin_stats")}
        </button>
      </div>

      {feedback && (
        <div className="ltx-pill" style={{ marginBottom: 16 }}>{feedback}</div>
      )}

      {tab === "users" && (
        <div>
          <p className="ltx-section-subtitle">{t("admin_users_sub")}</p>

          <div className="ltx-card" style={{ marginBottom: 16 }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>{t("admin_add_user")}</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 120px 100px", gap: 8 }}>
              <input className="ltx-field" placeholder={t("admin_username")} value={newUser.username}
                     onChange={(e) => setNewUser({ ...newUser, username: e.target.value })} />
              <input className="ltx-field" type="email" placeholder={t("admin_email")} value={newUser.email}
                     onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} />
              <input className="ltx-field" type="password" placeholder={t("password")} value={newUser.password}
                     onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} />
              <select className="ltx-field" value={newUser.role}
                      onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}>
                <option value="user">user</option>
                <option value="admin">admin</option>
              </select>
              <button type="button" onClick={addUser} className="ltx-primary">{t("admin_add_user")}</button>
            </div>
          </div>

          <div className="ltx-card" style={{ marginBottom: 16 }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>{t("admin_reset_pw")}</h3>
            <div style={{ display: "flex", gap: 8 }}>
              <input className="ltx-field" placeholder={t("admin_user_id")} style={{ flex: 1 }}
                  value={targetId} onChange={(e) => setTargetId(e.target.value)} />
              <input className="ltx-field" type="password" placeholder={t("admin_new_password")} style={{ flex: 2 }}
                  value={newPw} onChange={(e) => setNewPw(e.target.value)} />
              <button type="button" onClick={resetPw} className="ltx-secondary">{t("admin_reset_pw")}</button>
            </div>
          </div>

          <table className="ltx-table">
            <thead>
              <tr>
                <th>{t("admin_id")}</th><th>{t("admin_username")}</th><th>{t("admin_email")}</th>
                <th>{t("admin_role")}</th><th>{t("admin_active")}</th><th>{t("admin_last_login")}</th><th></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td>{u.username}{u.id === user.id ? " (you)" : ""}</td>
                  <td>{u.email ?? "—"}</td>
                  <td>
                    <span className="ltx-pill" data-status={u.role === "admin" ? "succeeded" : undefined}
                          style={u.role === "admin" ? { color: "var(--accent)", borderColor: "var(--accent)" } : undefined}>
                      {u.role}
                    </span>
                  </td>
                  <td>
                    <span className="ltx-pill" data-status={u.is_active ? "succeeded" : "failed"}>
                      {u.is_active ? "yes" : "no"}
                    </span>
                  </td>
                  <td>{u.last_login_at?.slice(0, 19).replace("T", " ") ?? "—"}</td>
                  <td>
                    {u.id !== user.id && (
                      <button type="button" onClick={() => toggleActive(u)} className="ltx-secondary"
                              style={{ padding: "4px 10px", fontSize: 12 }}>
                        {u.is_active ? "disable" : "enable"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "models" && (
        <div>
          <p className="ltx-section-subtitle">{t("admin_models_sub")}</p>

          <div className="ltx-card" style={{ marginBottom: 16 }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>{t("admin_download")}</h3>
            <div style={{ display: "flex", gap: 8 }}>
              <input className="ltx-field" placeholder="model id (e.g. ltx-13b-distilled)" style={{ flex: 1 }}
                  value={targetModelId} onChange={(e) => setTargetModelId(e.target.value)} />
              <button type="button" onClick={downloadModel} className="ltx-primary">{t("admin_download")}</button>
            </div>
            {downloadStatus && (
              <div className="ltx-pill" style={{ marginTop: 8, display: "inline-block" }}>{downloadStatus}</div>
            )}
          </div>

          <table className="ltx-table">
            <thead>
              <tr>
                <th>{t("admin_id")}</th><th>{t("admin_name")}</th><th>{t("admin_downloaded")}</th>
                <th>{t("admin_size")}</th><th>{t("admin_enabled")}</th><th>{t("admin_status")}</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => (
                <tr key={m.id}>
                  <td><code>{m.id}</code></td>
                  <td>{m.display_name}</td>
                  <td>{m.downloaded ? "✓" : "—"}</td>
                  <td>{m.downloaded ? `${m.size_gb} GB` : "—"}</td>
                  <td>{m.enabled ? "yes" : "no"}</td>
                  <td>{m.download_status?.status ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "stats" && stats && (
        <div>
          <p className="ltx-section-subtitle">{t("admin_stats_sub")}</p>
          <div className="ltx-card">
            <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>System</h3>
            <p><strong>GPU:</strong>{" "}
              {stats.gpu.available
                ? `${stats.gpu.name} · ${stats.gpu.vram_used_gb} / ${stats.gpu.vram_total_gb} GB`
                : "CUDA not available"}
            </p>
            <p><strong>Pipeline:</strong> <code>{stats.pipeline.current_id}</code></p>
            <p><strong>Disk (data):</strong> {stats.disk.data_free_gb} / {stats.disk.data_total_gb} GB free</p>
            <p><strong>Disk (models):</strong> {stats.disk.model_free_gb} / {stats.disk.model_total_gb} GB free</p>
            <p><strong>Users:</strong> {stats.users.active} active / {stats.users.total} total</p>
            <h3 style={{ margin: "16px 0 8px", fontSize: 14, fontWeight: 600 }}>Jobs</h3>
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              <li>queued: <strong>{stats.jobs.queued}</strong></li>
              <li>running: <strong>{stats.jobs.running}</strong></li>
              <li>succeeded: <strong>{stats.jobs.succeeded}</strong></li>
              <li>failed: <strong>{stats.jobs.failed}</strong></li>
            </ul>
            <h3 style={{ margin: "16px 0 8px", fontSize: 14, fontWeight: 600 }}>Recent activity</h3>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: 13 }}>
              {stats.recent_jobs.map((r) => (
                <li key={r.id} style={{ marginBottom: 4 }}>
                  <code>{r.id.slice(0, 12)}…</code> · {r.username} · {r.kind} ·{" "}
                  <span className="ltx-pill" data-status={r.status}>{r.status}</span> ·{" "}
                  {r.created_at?.slice(0, 19) ?? ""}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </AppShell>
  );
}