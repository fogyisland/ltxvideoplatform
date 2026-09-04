// lib/api.ts — typed wrapper over the FastAPI backend.
import type {
  AdminModel, AdminStats, AdminUser, Job, JobSummary, Model, Project, ProjectSummary, Scene, User,
} from "./types";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

type FetchOpts = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  form?: FormData;
  token?: string | null;
  signal?: AbortSignal;
};

async function request<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  if (opts.token) {
    headers["Authorization"] = `Bearer ${opts.token}`;
  }
  const res = await fetch(`${base}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body,
    signal: opts.signal,
  });
  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) {
    const detail = (data && typeof data === "object" && "detail" in (data as object))
      ? (data as { detail: unknown }).detail : res.statusText;
    throw new ApiError(res.status, data, String(detail));
  }
  return data as T;
}

function safeJson(text: string): unknown {
  try { return JSON.parse(text); } catch { return text; }
}

// ---------- auth ----------
export const api = {
  async login(username: string, password: string): Promise<{ access_token: string; expires_in: number }> {
    const form = new FormData();
    form.append("username", username);
    form.append("password", password);
    return request("/api/v1/auth/login", { method: "POST", form });
  },

  async signup(username: string, email: string, password: string): Promise<{ access_token: string; expires_in: number }> {
    return request("/api/v1/auth/signup", {
      method: "POST",
      body: { username, email, password },
    });
  },

  async me(token: string): Promise<User> {
    return request<User>("/api/v1/auth/me", { token });
  },

  // ---------- generation ----------
  async listModels(token: string): Promise<Model[]> {
    return request<Model[]>("/api/v1/models", { token });
  },

  async submitT2V(token: string, params: Record<string, unknown>): Promise<{ job_id: string }> {
    return request<{ job_id: string }>("/api/v1/t2v", { method: "POST", body: params, token });
  },

  async submitI2V(token: string, params: Record<string, unknown>): Promise<{ job_id: string }> {
    return request<{ job_id: string }>("/api/v1/i2v", { method: "POST", body: params, token });
  },

  async submitExtend(token: string, params: Record<string, unknown>): Promise<{ job_id: string }> {
    return request<{ job_id: string }>("/api/v1/extend", { method: "POST", body: params, token });
  },

  async getJob(token: string, jobId: string): Promise<Job> {
    return request<Job>(`/api/v1/jobs/${jobId}`, { token });
  },

  async cancelJob(token: string, jobId: string): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>(`/api/v1/jobs/${jobId}/cancel`, { method: "POST", token });
  },

  async uploadImage(token: string, file: File): Promise<{ id: string; path: string; sha256: string }> {
    const form = new FormData();
    form.append("file", file);
    return request<{ id: string; path: string; sha256: string }>(
      "/api/v1/uploads", { method: "POST", form, token },
    );
  },

  async listHistory(token: string, limit = 20): Promise<JobSummary[]> {
    return request<JobSummary[]>(`/api/v1/history?limit=${limit}`, { token });
  },

  // ---------- admin ----------
  async adminListUsers(token: string): Promise<AdminUser[]> {
    return request<AdminUser[]>("/api/v1/admin/users", { token });
  },

  async adminCreateUser(
    token: string,
    body: { username: string; email?: string | null; password: string; role: "user" | "admin" },
  ): Promise<AdminUser> {
    return request<AdminUser>("/api/v1/admin/users", { method: "POST", body, token });
  },

  async adminPatchUser(
    token: string,
    userId: number,
    body: { is_active?: boolean; role?: "user" | "admin" },
  ): Promise<AdminUser> {
    return request<AdminUser>(`/api/v1/admin/users/${userId}`, {
      method: "PATCH", body, token,
    });
  },

  async adminDeleteUser(token: string, userId: number): Promise<void> {
    await request(`/api/v1/admin/users/${userId}`, { method: "DELETE", token });
  },

  async adminResetPassword(
    token: string, userId: number, newPassword: string,
  ): Promise<void> {
    await request(`/api/v1/admin/users/${userId}/reset-password`, {
      method: "POST", body: { new_password: newPassword }, token,
    });
  },

  async adminListModels(token: string): Promise<AdminModel[]> {
    return request<AdminModel[]>("/api/v1/admin/models", { token });
  },

  async adminDownloadModel(
    token: string, modelId: string,
  ): Promise<{ model_id: string; status: string }> {
    return request(`/api/v1/admin/models/${modelId}/download`, { method: "POST", token });
  },

  async adminDownloadStatus(
    token: string, modelId: string,
  ): Promise<{
    status: "idle" | "running" | "done" | "failed";
    progress: number;
    message: string;
    current_file?: string;
    bytes_downloaded?: number;
    bytes_total?: number;
  }> {
    return request(`/api/v1/admin/models/${modelId}/download/status`, { token });
  },

  async adminStats(token: string): Promise<AdminStats> {
    return request<AdminStats>("/api/v1/admin/stats", { token });
  },

  // helpers
  resultUrl(token: string, jobId: string): string {
    const base = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:3381";
    return `${base}/api/v1/jobs/${jobId}/result`;
  },

  previewUrl(token: string, jobId: string): string {
    const base = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:3381";
    return `${base}/api/v1/jobs/${jobId}/preview`;
  },

  // ---------- projects / scenes ----------
  async listProjects(token: string): Promise<ProjectSummary[]> {
    return request<ProjectSummary[]>("/api/v1/projects", { token });
  },

  async createProject(token: string, body: { title: string; style?: string; model_id?: string }): Promise<Project> {
    return request<Project>("/api/v1/projects", { method: "POST", body, token });
  },

  async getProject(token: string, id: string): Promise<Project> {
    return request<Project>(`/api/v1/projects/${id}`, { token });
  },

  async patchProject(token: string, id: string, body: Partial<Pick<Project, "title" | "style" | "model_id" | "status">>): Promise<Project> {
    return request<Project>(`/api/v1/projects/${id}`, { method: "PATCH", body, token });
  },

  async deleteProject(token: string, id: string): Promise<void> {
    await request(`/api/v1/projects/${id}`, { method: "DELETE", token });
  },

  async addScene(token: string, projectId: string, body: { prompt?: string; image_upload_id?: string | null; duration?: string; quality?: string; position?: number }): Promise<Scene> {
    return request<Scene>(`/api/v1/projects/${projectId}/scenes`, { method: "POST", body, token });
  },

  async patchScene(token: string, projectId: string, sceneId: string, body: Partial<Pick<Scene, "prompt" | "image_upload_id" | "duration" | "quality" | "position">>): Promise<Scene> {
    return request<Scene>(`/api/v1/projects/${projectId}/scenes/${sceneId}`, { method: "PATCH", body, token });
  },

  async deleteScene(token: string, projectId: string, sceneId: string): Promise<void> {
    await request(`/api/v1/projects/${projectId}/scenes/${sceneId}`, { method: "DELETE", token });
  },

  async reorderScenes(token: string, projectId: string, sceneIds: string[]): Promise<Project> {
    return request<Project>(`/api/v1/projects/${projectId}/scenes/reorder`, {
      method: "POST", body: { scene_ids: sceneIds }, token,
    });
  },

  async generateScene(token: string, projectId: string, sceneId: string): Promise<Scene> {
    return request<Scene>(`/api/v1/projects/${projectId}/scenes/${sceneId}/generate`, {
      method: "POST", token,
    });
  },

  sceneVideoUrl(token: string, projectId: string, sceneId: string): string {
    const base = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:3381";
    return `${base}/api/v1/files/outputs/${token ? `?token=` : ""}`;
    // simpler: clients fetch via auth header; actual fetch done by callers
  },
};