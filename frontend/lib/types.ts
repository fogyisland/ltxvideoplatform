// lib/types.ts — shared TypeScript types matching FastAPI schemas.

export type Lang = "en" | "zh";

export type User = {
  id: number;
  username: string;
  email: string | null;
  role: "admin" | "user";
};

export type Model = {
  id: string;
  display_name: string;
  kind: string;
  default_steps: number;
  default_frames: number;
  vram_gb: number;
  enabled: boolean;
  description: string;
};

export type Job = {
  id: string;
  user_id: number;
  kind: string;
  model_id: string;
  params: Record<string, unknown>;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  progress: number;
  stage: string;
  error: string | null;
  output_path: string | null;
  preview_path: string | null;
  parent_job_id: string | null;
  duration_sec: number | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
};

export type JobSummary = {
  id: string;
  kind: string;
  model_id: string;
  status: Job["status"];
  created_at: string | null;
  output_path: string | null;
};

export type AdminUser = {
  id: number;
  username: string;
  email: string | null;
  role: "admin" | "user";
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
};

export type DownloadStatus = {
  status: "idle" | "running" | "done" | "failed";
  progress: number;        // 0..1
  message: string;
  current_file?: string;
  bytes_downloaded?: number;
  bytes_total?: number;
};

export type AdminModel = Model & {
  checkpoint_path: string;
  config_path: string;
  downloaded: boolean;
  size_gb: number;
  disk_size_gb: number;
  use_case: string;
  download_status: DownloadStatus;
};

export type AdminStats = {
  gpu: { name: string | null; vram_used_gb: number; vram_total_gb: number; available: boolean };
  disk: {
    data_free_gb: number; data_total_gb: number;
    model_free_gb: number; model_total_gb: number;
  };
  users: { total: number; active: number };
  jobs: { queued: number; running: number; succeeded: number; failed: number };
  pipeline: { current_id: string };
  recent_jobs: Array<{
    id: string;
    username: string;
    kind: string;
    model_id: string;
    status: Job["status"];
    created_at: string | null;
  }>;
  server_time: string;
};