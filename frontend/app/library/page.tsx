"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n";
import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import type { JobSummary } from "@/lib/types";

export default function LibraryPage() {
  const { token, loading, user } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const [items, setItems] = useState<JobSummary[] | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/signin");
  }, [loading, user, router]);

  useEffect(() => {
    if (!token) return;
    api.listHistory(token, 50).then(setItems).catch(() => setItems([]));
  }, [token]);

  if (loading || !user || !token) return null;

  const refresh = () => {
    if (!token) return;
    api.listHistory(token, 50).then(setItems);
  };

  return (
    <AppShell>
      <h2 className="ltx-section-title" style={{ marginTop: 0 }}>{t("library_title")}</h2>
      <p className="ltx-section-subtitle">{t("library_subtitle")}</p>

      <button onClick={refresh} className="ltx-secondary" type="button" style={{ marginBottom: 16 }}>
        {t("refresh")}
      </button>

      {!items || items.length === 0 ? (
        <div className="ltx-card" style={{ textAlign: "center", padding: 48, color: "var(--ink-1)" }}>
          {t("library_empty")}
        </div>
      ) : (
        <table className="ltx-table">
          <thead>
            <tr>
              <th>id</th>
              <th>kind</th>
              <th>model</th>
              <th>status</th>
              <th>created</th>
            </tr>
          </thead>
          <tbody>
            {items.map((j) => (
              <tr key={j.id}>
                <td><code>{j.id.slice(0, 12)}…</code></td>
                <td>{j.kind}</td>
                <td>{j.model_id}</td>
                <td>
                  <span className="ltx-pill" data-status={j.status}>{j.status}</span>
                </td>
                <td>{j.created_at?.slice(0, 19).replace("T", " ") ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </AppShell>
  );
}