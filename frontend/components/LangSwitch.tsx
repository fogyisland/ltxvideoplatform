"use client";
import { useI18n } from "@/lib/i18n";
import type { Lang } from "@/lib/types";

export function LangSwitch() {
  const { lang, setLang, t } = useI18n();
  const target = (l: Lang) => () => setLang(l);
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <button
        type="button"
        className="ltx-lang-btn"
        data-active={lang === "en"}
        onClick={target("en")}
      >
        English
      </button>
      <button
        type="button"
        className="ltx-lang-btn"
        data-active={lang === "zh"}
        onClick={target("zh")}
      >
        {lang === "zh" ? "中文" : "中文"}
      </button>
    </div>
  );
}

export function LangSwitchCompact() {
  const { lang, setLang } = useI18n();
  return (
    <div style={{ display: "flex", gap: 4 }}>
      <button
        type="button"
        onClick={() => setLang("en")}
        className="ltx-lang-btn"
        data-active={lang === "en"}
        style={{ padding: "4px 10px", fontSize: 11 }}
      >
        EN
      </button>
      <button
        type="button"
        onClick={() => setLang("zh")}
        className="ltx-lang-btn"
        data-active={lang === "zh"}
        style={{ padding: "4px 10px", fontSize: 11 }}
      >
        中
      </button>
    </div>
  );
}