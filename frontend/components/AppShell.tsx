"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n";
import { LangSwitch } from "./LangSwitch";
import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  const pathname = usePathname();
  const router = useRouter();

  const navCls = (href: string) => `ltx-nav-link${pathname === href ? " active" : ""}`;
  const isAdmin = user?.role === "admin";

  const onSignOut = () => {
    logout();
    router.push("/signin");
  };

  return (
    <div style={{ maxWidth: 980, margin: "0 auto", padding: "0 24px" }}>
      {/* Top bar */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "24px 0 12px",
          borderBottom: "1px solid var(--line)",
          marginBottom: 24,
        }}
      >
        <Link href="/create" style={{ textDecoration: "none", color: "var(--ink-0)" }}>
          <span style={{ fontFamily: "var(--font-serif)", fontSize: 22, fontWeight: 600 }}>
            <span className="ltx-mark" />
            {t("app_name")}
          </span>
        </Link>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontSize: 13, color: "var(--ink-1)" }}>
            {user?.username}
            {isAdmin && (
              <span
                className="ltx-pill"
                style={{ marginLeft: 8, color: "var(--accent)", borderColor: "var(--accent)" }}
              >
                admin
              </span>
            )}
          </span>
          <LangSwitch />
          <button onClick={onSignOut} className="ltx-secondary" type="button">
            {t("nav_signout")}
          </button>
        </div>
      </header>

      {/* Nav */}
      <nav style={{ display: "flex", gap: 24, marginBottom: 24 }}>
        <Link href="/create" className={navCls("/create")} style={{ textDecoration: "none" }}>
          {t("nav_create")}
        </Link>
        <Link href="/projects" className={navCls("/projects")} style={{ textDecoration: "none" }}>
          {t("nav_projects")}
        </Link>
        <Link href="/library" className={navCls("/library")} style={{ textDecoration: "none" }}>
          {t("nav_library")}
        </Link>
        {isAdmin && (
          <Link href="/admin" className={navCls("/admin")} style={{ textDecoration: "none" }}>
            {t("nav_admin")}
          </Link>
        )}
      </nav>

      {/* Content */}
      <main style={{ paddingBottom: 80 }}>{children}</main>
    </div>
  );
}