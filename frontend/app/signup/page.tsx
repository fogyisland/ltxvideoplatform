"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth, ApiError } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n";
import { LangSwitch } from "@/components/LangSwitch";

export default function SignUp() {
  const { signup } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await signup(username, email, password);
      router.replace("/create");
    } catch (e) {
      setErr(e instanceof ApiError ? t("err_signup_failed") : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 460, margin: "80px auto", padding: "0 24px" }}>
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
          {t("signup_title")}
        </h2>
        <p className="ltx-section-subtitle">{t("signup_subtitle")}</p>
        <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label className="ltx-label">{t("username")}</label>
            <input
              className="ltx-field"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              pattern="[A-Za-z0-9_.\-]{3,32}"
              required
            />
          </div>
          <div>
            <label className="ltx-label">{t("email")}</label>
            <input
              className="ltx-field"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="ltx-label">{t("password")}</label>
            <input
              className="ltx-field"
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
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
            {busy ? "…" : t("signup_btn")}
          </button>
        </form>
        <p style={{ marginTop: 16, fontSize: 13, color: "var(--ink-1)", textAlign: "center" }}>
          {t("have_account")}{" "}
          <Link href="/signin" style={{ color: "var(--accent)" }}>
            {t("signin")}
          </Link>
        </p>
      </div>
    </div>
  );
}