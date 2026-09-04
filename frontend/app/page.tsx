"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n";
import { LangSwitch } from "@/components/LangSwitch";

export default function Landing() {
  const { user, loading } = useAuth();
  const { t } = useI18n();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) router.replace("/create");
  }, [loading, user, router]);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--bg-0)",
        padding: "80px 24px",
      }}
    >
      <div
        style={{
          maxWidth: 640,
          margin: "0 auto",
          textAlign: "center",
          color: "var(--ink-0)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 32 }}>
          <LangSwitch />
        </div>
        <h1
          className="ltx-hero-title"
          style={{ fontSize: 56, textAlign: "center" }}
        >
          {t("landing_title")}
        </h1>
        <p
          className="ltx-hero-subtitle"
          style={{ textAlign: "center", marginTop: 16, fontSize: 18 }}
        >
          {t("landing_subtitle")}
        </p>

        <div style={{ marginTop: 48, display: "flex", justifyContent: "center", gap: 12 }}>
          <a
            href="/signin"
            className="ltx-primary"
            style={{ textDecoration: "none", display: "inline-block" }}
          >
            {t("landing_cta_signin")}
          </a>
          <a
            href="/signup"
            className="ltx-secondary"
            style={{ textDecoration: "none", display: "inline-block" }}
          >
            {t("landing_cta_signup")}
          </a>
        </div>
        <p
          style={{
            marginTop: 32,
            color: "var(--ink-2)",
            fontSize: 13,
          }}
        >
          {t("landing_hint")}
        </p>
      </div>
    </div>
  );
}