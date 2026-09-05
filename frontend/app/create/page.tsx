"use client";
import type { SystemInfo, InferenceMode } from "@/lib/types";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useI18n } from "@/lib/i18n";
import { AppShell } from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";
import type { Job, Model } from "@/lib/types";

type Style = "Cinematic" | "Animated" | "Realistic" | "Dreamy";
type Mode = "text" | "image";
type Duration = "short" | "medium" | "long";
type Quality = "draft" | "standard" | "high";
type Size = "small" | "medium";

const STYLE_KEYS = ["style_cinematic", "style_animated", "style_realistic", "style_dreamy"] as const;

const DURATION_FRAMES: Record<Duration, number> = { short: 97, medium: 161, long: 241 };
const QUALITY_STEPS: Record<Quality, number> = { draft: 8, standard: 20, high: 40 };
const SIZE_HW: Record<Size, [number, number]> = { small: [384, 640], medium: [480, 768] };

export default function CreatePage() {
  const { t, lang, examples } = useI18n();
  const { token, loading, user } = useAuth();
  const router = useRouter();

  const [mode, setMode] = useState<Mode>("text");
  const [prompt, setPrompt] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imageStrength, setImageStrength] = useState(0.85);
  const [style, setStyle] = useState<Style>("Cinematic");
  const [duration, setDuration] = useState<Duration>("medium");
  const [quality, setQuality] = useState<Quality>("standard");
  const [size, setSize] = useState<Size>("medium");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [models, setModels] = useState<Model[]>([]);
  const [result, setResult] = useState<{ url: string; jobId: string } | null>(null);
  const [progress, setProgress] = useState<{ p: number; stage: string; status: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/signin");
  }, [loading, user, router]);

  useEffect(() => {
    if (!token) return;
    api.listModels(token).then(setModels).catch(() => setModels([]));
  }, [token]);

  const [sysInfo, setSysInfo] = useState<SystemInfo | null>(null);
  const [inferenceMode, setInferenceMode] = useState<InferenceMode>("auto");
  useEffect(() => {
    api.systemInfo().then(setSysInfo).catch(() => setSysInfo(null));
  }, []);

  if (loading || !user || !token) {
    return <div style={{ padding: 40, textAlign: "center", color: "var(--ink-1)" }}>…</div>;
  }

  const buildPrompt = (text: string) => {
    if (!text) return text;
    const styleLabel = STYLE_KEYS[STYLE_KEYS.indexOf(style as typeof STYLE_KEYS[number])]
      ? t(STYLE_KEYS[STYLE_KEYS.indexOf(style as typeof STYLE_KEYS[number])])
      : style;
    const prefix = lang === "zh" ? `风格：${styleLabel}。 ` : `Style: ${styleLabel}. `;
    return prefix + text;
  };

  const onCreate = async () => {
    setErr(null);
    if (!prompt.trim()) { setErr(t("err_no_prompt")); return; }
    setBusy(true);
    setResult(null);
    setProgress({ p: 0, stage: "queued", status: "queued" });
    const modelId = models.find((m) => m.enabled)?.id || "ltx-2b-distilled";
    const [h, w] = SIZE_HW[size];
    const numFrames = DURATION_FRAMES[duration];
    const steps = QUALITY_STEPS[quality];
    const fullPrompt = buildPrompt(prompt);

    try {
      let jobId: string;
      if (mode === "text") {
        const r = await api.submitT2V(token, {
          model_id: modelId, prompt: fullPrompt,
          num_frames: numFrames, height: h, width: w,
          num_inference_steps: steps, guidance_scale: 5.0, fps: 24,
        }, inferenceMode);
        jobId = r.job_id;
      } else {
        if (!imageFile) { setErr(t("err_no_image")); setBusy(false); return; }
        const up = await api.uploadImage(token, imageFile);
        const r = await api.submitI2V(token, {
          model_id: modelId, image_upload_id: up.id, prompt: fullPrompt,
          strength: imageStrength, num_frames: numFrames,
          num_inference_steps: steps, guidance_scale: 5.0, fps: 24,
        }, inferenceMode);
        jobId = r.job_id;
      }
      // poll
      const start = Date.now();
      while (Date.now() - start < 600_000) {
        const j = await api.getJob(token, jobId);
        setProgress({ p: j.progress, stage: j.stage, status: j.status });
        if (j.status === "succeeded") {
          setResult({ url: api.resultUrl(token, jobId), jobId });
          break;
        }
        if (j.status === "failed" || j.status === "cancelled") {
          setErr(j.error || t("err_failed"));
          break;
        }
        await new Promise((r) => setTimeout(r, 1500));
      }
    } catch (e) {
      setErr(e instanceof ApiError ? `${e.status}: ${e.message}` : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onExtend = async () => {
    if (!result) return;
    setBusy(true);
    setErr(null);
    try {
      const modelId = models.find((m) => m.enabled)?.id || "ltx-2b-distilled";
      const r = await api.submitExtend(token, {
        parent_job_id: result.jobId, prompt: "", num_frames: 97,
        num_inference_steps: 20, guidance_scale: 5.0, fps: 24,
      });
      const start = Date.now();
      while (Date.now() - start < 600_000) {
        const j = await api.getJob(token, r.job_id);
        setProgress({ p: j.progress, stage: j.stage, status: j.status });
        if (j.status === "succeeded") {
          setResult({ url: api.resultUrl(token, r.job_id), jobId: r.job_id });
          break;
        }
        if (j.status === "failed" || j.status === "cancelled") {
          setErr(j.error || t("err_failed"));
          break;
        }
        await new Promise((r) => setTimeout(r, 1500));
      }
    } catch (e) {
      setErr(e instanceof ApiError ? `${e.status}: ${e.message}` : String(e));
    } finally {
      setBusy(false);
    }
  };

  const styleNames = STYLE_KEYS.map((k) => t(k)) as string[];
  const styles: Style[] = ["Cinematic", "Animated", "Realistic", "Dreamy"];

  return (
    <AppShell>
      <h1 className="ltx-hero-title">{t("hero_create_title")}</h1>
      <p className="ltx-hero-subtitle" style={{ marginBottom: 32 }}>{t("hero_create_subtitle")}</p>

      {/* Mode toggle */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button
          type="button"
          onClick={() => setMode("text")}
          className="ltx-chip"
          data-active={mode === "text"}
        >
          {t("mode_text")}
        </button>
        <button
          type="button"
          onClick={() => setMode("image")}
          className="ltx-chip"
          data-active={mode === "image"}
        >
          {t("mode_image")}
        </button>
      </div>

      {mode === "text" ? (
        <div>
          <label className="ltx-label">{t("prompt_label")}</label>
          <textarea
            className="ltx-input"
            value={prompt}
            placeholder={t("prompt_placeholder")}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
          />

          <p className="ltx-section-subtitle" style={{ marginTop: 24 }}>
            {t("prompt_examples")}
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {examples.map((p, i) => (
              <button key={i} type="button" className="ltx-example" onClick={() => setPrompt(p)}>
                {p}
              </button>
            ))}
          </div>

          <p className="ltx-section-subtitle" style={{ marginTop: 24 }}>{t("style_label")}</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {styles.map((s, i) => (
              <button
                key={s}
                type="button"
                className="ltx-chip"
                data-active={style === s}
                onClick={() => setStyle(s)}
              >
                {styleNames[i]}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", gap: 12, marginTop: 32 }}>
            <button onClick={onCreate} disabled={busy} className="ltx-primary" type="button">
              {busy ? `${t("creating")} · ${Math.round((progress?.p ?? 0) * 100)}%` : t("create_btn")}
            </button>
            {result && (
              <button onClick={onExtend} disabled={busy} className="ltx-secondary" type="button">
                {t("make_longer")}
              </button>
            )}
          </div>

          {progress && busy && (
            <div className="ltx-progress" style={{ marginTop: 16 }}>
              <div style={{ width: `${progress.p * 100}%` }} />
            </div>
          )}
          {err && (
            <div className="ltx-pill" data-status="failed" style={{ display: "block", padding: "8px 12px", marginTop: 16 }}>
              {err}
            </div>
          )}
          {result && (
            <div className="ltx-card" style={{ marginTop: 24 }}>
              <p className="ltx-section-subtitle">{t("result_label")}</p>
              <video src={result.url} controls style={{ width: "100%", borderRadius: 8 }} />
              <p style={{ marginTop: 8, fontSize: 12, color: "var(--ink-2)" }}>
                job_id: <code>{result.jobId}</code>
              </p>
            </div>
          )}
        </div>
      ) : (
        <div>
          <label className="ltx-label">{t("image_upload")}</label>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setImageFile(e.target.files?.[0] || null)}
            style={{ marginBottom: 12 }}
          />
          <label className="ltx-label">{t("image_prompt_help")}</label>
          <textarea
            className="ltx-input"
            value={prompt}
            placeholder={t("prompt_placeholder")}
            onChange={(e) => setPrompt(e.target.value)}
            rows={2}
            style={{ marginBottom: 12 }}
          />
          <label className="ltx-label">{t("image_strength")} ({imageStrength.toFixed(2)})</label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={imageStrength}
            onChange={(e) => setImageStrength(Number(e.target.value))}
            style={{ width: "100%", accentColor: "var(--accent)" }}
          />

          <button onClick={onCreate} disabled={busy || !imageFile} className="ltx-primary" type="button" style={{ marginTop: 24 }}>
            {busy ? `${t("creating")} · ${Math.round((progress?.p ?? 0) * 100)}%` : t("create_btn")}
          </button>
        </div>
      )}

      {/* Advanced options disclosure */}
      <details
        open={showAdvanced}
        onToggle={(e) => setShowAdvanced((e.target as HTMLDetailsElement).open)}
        style={{ marginTop: 32 }}
      >
        <summary
          style={{ cursor: "pointer", color: "var(--ink-1)", fontSize: 13, padding: "8px 0" }}
        >
          {showAdvanced ? "▾" : "▸"} {t("more_options")}
        </summary>
        <div style={{ padding: 16, background: "var(--bg-1)", border: "1px solid var(--line)", borderRadius: 8 }}>
          <div style={{ marginBottom: 12 }}>
            <label className="ltx-label">{t("duration_label")}</label>
            <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
              {(["short", "medium", "long"] as Duration[]).map((d) => (
                <button
                  key={d}
                  type="button"
                  className="ltx-chip"
                  data-active={duration === d}
                  onClick={() => setDuration(d)}
                >
                  {t(`duration_${d}`)}
                </button>
              ))}
            </div>
          </div>
          <div style={{ marginBottom: 12 }}>
            <label className="ltx-label">{t("quality_label")}</label>
            <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
              {(["draft", "standard", "high"] as Quality[]).map((q) => (
                <button
                  key={q}
                  type="button"
                  className="ltx-chip"
                  data-active={quality === q}
                  onClick={() => setQuality(q)}
                >
                  {t(`quality_${q}`)}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="ltx-label">{t("size_label")}</label>
            <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
              {(["small", "medium"] as Size[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  className="ltx-chip"
                  data-active={size === s}
                  onClick={() => setSize(s)}
                >
                  {t(`size_${s}`)}
                </button>
              ))}
            </div>
          </div>
        </div>
      </details>

      <p
        style={{
          marginTop: 40,
          color: "var(--ink-2)",
          fontSize: 12,
          textAlign: "center",
        }}
      >
        {t("powered_by")}
      </p>
    </AppShell>
  );
}