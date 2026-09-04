// lib/auth-context.tsx — holds JWT + user; persists in localStorage.
"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { User } from "./types";

type Auth = {
  token: string | null;
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  signup: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthCtx = createContext<Auth>({
  token: null, user: null, loading: true,
  login: async () => {}, signup: async () => {}, logout: () => {},
});

const KEY_TOKEN = "ltx_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const t = window.localStorage.getItem(KEY_TOKEN);
    if (!t) { setLoading(false); return; }
    api.me(t).then((u) => { setToken(t); setUser(u); }).catch(() => {
      window.localStorage.removeItem(KEY_TOKEN);
    }).finally(() => setLoading(false));
  }, []);

  const persist = (t: string | null) => {
    setToken(t);
    if (typeof window !== "undefined") {
      if (t) window.localStorage.setItem(KEY_TOKEN, t);
      else window.localStorage.removeItem(KEY_TOKEN);
    }
  };

  const login = useCallback(async (username: string, password: string) => {
    const r = await api.login(username, password);
    persist(r.access_token);
    const u = await api.me(r.access_token);
    setUser(u);
  }, []);

  const signup = useCallback(async (username: string, email: string, password: string) => {
    const r = await api.signup(username, email, password);
    persist(r.access_token);
    const u = await api.me(r.access_token);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    persist(null);
    setUser(null);
  }, []);

  return (
    <AuthCtx.Provider value={{ token, user, loading, login, signup, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth(): Auth {
  return useContext(AuthCtx);
}

export { ApiError };