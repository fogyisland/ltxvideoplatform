"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

// Dev-only page: auto-logs in with credentials from query params, then redirects.
function DevLoginInner() {
  const params = useSearchParams();
  const router = useRouter();
  const { login } = useAuth();
  const [status, setStatus] = useState("logging in…");

  useEffect(() => {
    const u = params.get("u");
    const p = params.get("p");
    const next = params.get("next") || "/create";
    if (!u || !p) {
      setStatus("missing credentials; pass ?u=USER&p=PASS&next=/path");
      return;
    }
    login(u, p).then(() => {
      router.replace(next);
    }).catch((e) => {
      setStatus(`failed: ${e.message ?? e}`);
    });
  }, [params, login, router]);

  return (
    <div style={{ padding: 40, textAlign: "center", color: "var(--ink-1)" }}>
      {status}
    </div>
  );
}

export default function DevLogin() {
  return (
    <Suspense fallback={<div style={{ padding: 40, color: "var(--ink-1)" }}>loading…</div>}>
      <DevLoginInner />
    </Suspense>
  );
}