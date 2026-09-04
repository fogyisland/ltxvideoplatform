"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth, ApiError } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n";
import { LangSwitch } from "@/components/LangSwitch";

export default function SignIn() {
  const { login } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login(username, password);
      router.replace("/create");
    } catch (e) {
      setErr(e instanceof ApiError ? t("err_signin_failed") : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 420, margin: "80px auto", padding: "0 24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <Link href="/" style={{ textDecoration: "none" }}>
          <span style={{ fontFamily: "var(--font-serif)", fontSize: 20, fontWeight: 600 }}>
            <span className="ltx-mark" />
            {t("app_name")}
          </span>
        </Link>
        <LangSwitch />
      </div>
      <div className="ltx-card">
        <h2 className="ltx-hero-title" style={{ fontSize: 26 }}>
          {t("signin_title")}
        </h2>
        <p className="ltx-section-subtitle">{t("signin_subtitle")}</p>
        <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label className="ltx-label">{t("username")}</label>
            <input
              className="ltx-field"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              autoComplete="username"
              required
            />
          </div>
          <div>
            <label className="ltx-label">{t("password")}</label>
            <input
              className="ltx-field"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          {err && (
            <div
              className="ltx-pill"
              data-status="failed"
              style={{ display: "block", padding: "8px 12px" }}
            >
              {err}
            </div>
          )}
          <button type="submit" className="ltx-primary" disabled={busy}>
            {busy ? "…" : t("signin_btn")}
          </button>
        </form>
        <p style={{ marginTop: 16, fontSize: 13, color: "var(--ink-1)", textAlign: "center" }}>
          {t("no_account")}{" "}
          <Link href="/signup" style={{ color: "var(--accent)" }}>
            {t("landing_cta_signup")}
          </Link>
        </p>
      </div>
    </div>
  );
}