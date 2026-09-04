// lib/api-context.tsx — exposes API base URL via React context.
"use client";
import { createContext, useContext } from "react";

const Ctx = createContext<string>("http://127.0.0.1:8000");

export function ApiBaseProvider({ children }: { children: React.ReactNode }) {
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
  return <Ctx.Provider value={base}>{children}</Ctx.Provider>;
}

export function useApiBase(): string {
  return useContext(Ctx);
}