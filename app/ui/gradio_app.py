# app/ui/gradio_app.py
"""Gradio UI for LTX-Video Web Platform.

Designed for non-technical creators. One page, plain language, single
primary action. Advanced controls hidden by default behind a "More options"
toggle. Bilingual EN/中文 with a small switcher in the header.
"""
from __future__ import annotations
import gradio as gr

from app.config import get_settings
from app.ui.api_client import ApiClient


# ---------- i18n ------------------------------------------------------------

I18N = {
    "en": {
        "app_name": "LTX Studio",
        "hero_title": "What do you want to create?",
        "hero_subtitle": "Type a description, pick a style, and we'll make a short video.",
        "prompt_label": "Describe your video",
        "prompt_placeholder": "e.g. a cat playing piano in a jazz club",
        "prompt_examples": "Need inspiration? Try one of these:",
        "style_label": "Style",
        "styles": ["Cinematic", "Animated", "Realistic", "Dreamy"],
        "create": "Create video",
        "creating": "Creating your video",
        "result_label": "Your video",
        "make_another": "Make another",
        "make_longer": "Make it longer",
        "more_options": "More options",
        "fewer_options": "Fewer options",
        "duration_label": "Length",
        "quality_label": "Quality",
        "size_label": "Size",
        "short": "short · ~5s",
        "medium": "medium · ~10s",
        "long": "long · ~20s",
        "draft": "draft · fast",
        "standard": "standard",
        "high": "high · slow",
        "small": "small · 480p",
        "medium_res": "medium · 720p",
        "library": "Library",
        "library_empty": "Your creations will appear here.\nMake your first video to get started.",
        "library_subtitle": "Videos you've made before",
        "tab_create": "Create",
        "tab_library": "Library",
        "tab_admin": "Admin",
        "signin": "Sign in",
        "signin_title": "Welcome back",
        "signin_subtitle": "Sign in to save your creations",
        "username": "username",
        "password": "password",
        "signin_btn": "Sign in",
        "signout": "Sign out",
        "signed_in_as": "Signed in as {name}",
        "start_from_image": "Start from an image",
        "start_from_image_help": "Upload a picture and we'll bring it to life.",
        "image_upload": "Choose a starting image",
        "image_prompt_help": "What should happen in the video?",
        "image_strength": "How much to change from the original",
        "language": "language",
        "powered_by": "powered by LTX-Video",
        "err_no_login": "Please sign in first.",
        "err_no_prompt": "Please describe your video.",
        "err_no_image": "Please choose a starting image.",
        "err_failed": "Something went wrong. Try again.",
        "queue_position": "In the queue · position {n}",
        "style_appended": "Style: {style}",
        "admin_users": "Users",
        "admin_models": "Models",
        "admin_stats": "System",
        "admin_users_subtitle": "Create accounts, reset passwords, enable or disable users",
        "admin_models_subtitle": "Download and enable model variants",
        "admin_stats_subtitle": "GPU, disk, queue and recent jobs",
        "admin_username": "username",
        "admin_email": "email (optional)",
        "admin_password": "password",
        "admin_role": "role",
        "admin_add_user": "Add user",
        "admin_user_id": "user id",
        "admin_new_password": "new password",
        "admin_reset_pw": "Reset password",
        "admin_toggle_active": "Toggle active",
        "admin_delete": "Disable",
        "admin_download": "Download",
        "admin_refresh": "Refresh",
        "admin_user_table": "id | username | email | role | active | last login",
        "admin_model_table": "id | name | downloaded | size | enabled | status",
        "admin_signup_title": "Create your account",
        "admin_signup_subtitle": "Sign up to start creating",
        "admin_signup_email": "email",
        "admin_signup_password": "password (8+ chars)",
        "admin_signup_btn": "Sign up",
        "admin_have_account": "Already have an account? Sign in",
        "admin_no_account": "New here? Create an account",
        "admin_landing_title": "LTX Studio",
        "admin_landing_subtitle": "Generate short videos from text prompts — running on your own GPU.",
        "admin_landing_cta_signin": "Sign in",
        "admin_landing_cta_signup": "Create account",
    },
    "zh": {
        "app_name": "LTX 工作室",
        "hero_title": "想创作什么？",
        "hero_subtitle": "描述一下，选个风格，我们来生成短视频。",
        "prompt_label": "描述你的视频",
        "prompt_placeholder": "例如：一只猫在爵士酒吧弹钢琴",
        "prompt_examples": "没灵感？试试这些：",
        "style_label": "风格",
        "styles": ["电影感", "动画", "写实", "梦幻"],
        "create": "生成视频",
        "creating": "正在生成",
        "result_label": "你的视频",
        "make_another": "再做一条",
        "make_longer": "延展时长",
        "more_options": "更多选项",
        "fewer_options": "收起选项",
        "duration_label": "时长",
        "quality_label": "画质",
        "size_label": "尺寸",
        "short": "短 · 约 5 秒",
        "medium": "中 · 约 10 秒",
        "long": "长 · 约 20 秒",
        "draft": "草稿 · 快速",
        "standard": "标准",
        "high": "高清 · 慢",
        "small": "小 · 480p",
        "medium_res": "中 · 720p",
        "library": "作品库",
        "library_empty": "你的创作将出现在这里。\n先生成一条视频试试。",
        "library_subtitle": "你之前做过的视频",
        "tab_create": "创作",
        "tab_library": "作品库",
        "tab_admin": "管理",
        "signin": "登录",
        "signin_title": "欢迎回来",
        "signin_subtitle": "登录后可以保存你的创作",
        "username": "用户名",
        "password": "密码",
        "signin_btn": "登录",
        "signout": "退出",
        "signed_in_as": "已登录：{name}",
        "start_from_image": "从图片开始",
        "start_from_image_help": "上传一张图片，让它动起来。",
        "image_upload": "选择起始图片",
        "image_prompt_help": "视频里应该发生什么？",
        "image_strength": "相对原图的变化程度",
        "language": "语言",
        "powered_by": "由 LTX-Video 提供算力",
        "err_no_login": "请先登录。",
        "err_no_prompt": "请描述你的视频。",
        "err_no_image": "请选择一张起始图片。",
        "err_failed": "出错了，重试一下。",
        "queue_position": "排队中 · 第 {n} 位",
        "style_appended": "风格：{style}",
        "admin_users": "用户",
        "admin_models": "模型",
        "admin_stats": "系统",
        "admin_users_subtitle": "创建账号、重置密码、启用或禁用用户",
        "admin_models_subtitle": "下载和启用模型变体",
        "admin_stats_subtitle": "GPU、磁盘、队列和最近任务",
        "admin_username": "用户名",
        "admin_email": "邮箱（可选）",
        "admin_password": "密码",
        "admin_role": "角色",
        "admin_add_user": "添加用户",
        "admin_user_id": "用户 ID",
        "admin_new_password": "新密码",
        "admin_reset_pw": "重置密码",
        "admin_toggle_active": "切换启用",
        "admin_delete": "禁用",
        "admin_download": "下载",
        "admin_refresh": "刷新",
        "admin_user_table": "ID | 用户名 | 邮箱 | 角色 | 启用 | 最近登录",
        "admin_model_table": "ID | 名称 | 已下载 | 大小 | 启用 | 状态",
        "admin_signup_title": "创建账号",
        "admin_signup_subtitle": "注册后即可开始创作",
        "admin_signup_email": "邮箱",
        "admin_signup_password": "密码（至少 8 位）",
        "admin_signup_btn": "注册",
        "admin_have_account": "已有账号？登录",
        "admin_no_account": "新用户？创建账号",
        "admin_landing_title": "LTX 工作室",
        "admin_landing_subtitle": "用文字描述生成短视频 — 跑在你自己的 GPU 上。",
        "admin_landing_cta_signin": "登录",
        "admin_landing_cta_signup": "注册账号",
    },
}

EXAMPLE_PROMPTS_EN = [
    "a cat playing piano in a jazz club",
    "aerial view of mountains at sunset",
    "a robot painting a self-portrait",
    "time-lapse of a flower blooming",
]
EXAMPLE_PROMPTS_ZH = [
    "一只猫在爵士酒吧弹钢琴",
    "航拍山脉日落",
    "机器人在画自画像",
    "花朵绽放的延时摄影",
]


def t(key: str, lang: str = "en", **fmt) -> str:
    text = I18N.get(lang, I18N["en"]).get(key, key)
    return text.format(**fmt) if fmt else text


def example_prompts(lang: str) -> list[str]:
    return EXAMPLE_PROMPTS_ZH if lang == "zh" else EXAMPLE_PROMPTS_EN


def _client(state) -> ApiClient:
    base = f"http://127.0.0.1:{get_settings().app_port_api}"
    return ApiClient(base, token=state.get("token"))


# ---------- design tokens --------------------------------------------------

CSS = """
:root {
  --bg-0: #F8F5F0;
  --bg-1: #FFFFFF;
  --bg-2: #F2EEE7;
  --ink-0: #2B2926;
  --ink-1: #6B6660;
  --ink-2: #A8A39C;
  --accent: #4A6B7C;
  --accent-soft: #E8EEF1;
  --warm: #C9A86A;
  --good: #7A9F6E;
  --line: #E0DAD1;
  --shadow: 0 1px 0 rgba(43, 41, 38, 0.04), 0 8px 24px rgba(43, 41, 38, 0.04);
}
html, body {
  background: var(--bg-0) !important;
  color: var(--ink-0) !important;
}
.gradio-container, .gradio-container > .main, .gradio-container > .main > .wrap {
  background: var(--bg-0) !important;
  color: var(--ink-0) !important;
  font-family: 'Inter', system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
  max-width: 980px !important;
  margin: 0 auto !important;
}
.dark { background: var(--bg-0) !important; }
.block, .panel, .form, .gap, .group, .border, .container {
  background: transparent !important;
  border-color: var(--line) !important;
  box-shadow: none !important;
}

/* Typography */
h1, h2, h3, h4 { color: var(--ink-0) !important; }
.hero-title {
  font-family: 'Source Serif 4', 'Source Serif Pro', 'Songti SC', 'Noto Serif CJK SC', serif !important;
  font-size: 38px !important;
  font-weight: 600 !important;
  letter-spacing: -0.02em !important;
  color: var(--ink-0) !important;
  line-height: 1.15 !important;
  margin: 0 0 8px 0 !important;
}
.hero-subtitle {
  font-size: 16px !important;
  color: var(--ink-1) !important;
  font-weight: 400 !important;
  margin: 0 !important;
}
.section-title {
  font-family: 'Source Serif 4', 'Source Serif Pro', 'Songti SC', serif !important;
  font-size: 22px !important;
  font-weight: 600 !important;
  color: var(--ink-0) !important;
  margin: 32px 0 16px 0 !important;
}
.section-subtitle {
  font-size: 13px !important;
  color: var(--ink-1) !important;
  margin: 0 0 16px 0 !important;
}

label, .label, .prose, .markdown, .md, p, span, div, button, input, textarea, select {
  color: var(--ink-0) !important;
}
label.block-label {
  color: var(--ink-0) !important;
  font-size: 14px !important;
  font-weight: 500 !important;
}

/* Header */
.app-header {
  padding: 24px 0 8px 0 !important;
  border-bottom: 1px solid var(--line) !important;
  margin-bottom: 32px !important;
}
.app-name {
  font-family: 'Source Serif 4', 'Source Serif Pro', 'Songti SC', serif !important;
  font-size: 22px !important;
  font-weight: 600 !important;
  letter-spacing: -0.01em !important;
  color: var(--ink-0) !important;
}
.app-name .accent-dot {
  display: inline-block !important;
  width: 6px !important; height: 6px !important;
  background: var(--warm) !important;
  border-radius: 50% !important;
  margin-right: 8px !important;
  vertical-align: middle !important;
  position: relative !important;
  top: -2px !important;
}

/* Language switcher — small, subtle */
.lang-btn {
  background: transparent !important;
  border: 1px solid var(--line) !important;
  color: var(--ink-1) !important;
  font-size: 12px !important;
  font-weight: 500 !important;
  padding: 6px 12px !important;
  border-radius: 999px !important;
  height: auto !important;
  min-height: 0 !important;
  letter-spacing: 0.02em !important;
}
.lang-btn.lang-active {
  background: var(--accent-soft) !important;
  color: var(--accent) !important;
  border-color: var(--accent) !important;
}

/* Sign-in button — secondary */
.signin-btn {
  background: transparent !important;
  border: 1px solid var(--line) !important;
  color: var(--ink-0) !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  padding: 8px 16px !important;
  border-radius: 999px !important;
  height: auto !important;
  min-height: 0 !important;
}
.signin-btn:hover {
  background: var(--bg-2) !important;
  border-color: var(--ink-2) !important;
}

/* Big prompt input */
.big-prompt textarea {
  font-size: 17px !important;
  line-height: 1.5 !important;
  padding: 16px 20px !important;
  border: 1px solid var(--line) !important;
  border-radius: 12px !important;
  background: var(--bg-1) !important;
  box-shadow: var(--shadow) !important;
  color: var(--ink-0) !important;
  font-family: 'Inter', system-ui, sans-serif !important;
  min-height: 88px !important;
}
.big-prompt textarea:focus {
  border-color: var(--accent) !important;
  outline: none !important;
  box-shadow: var(--shadow), 0 0 0 3px var(--accent-soft) !important;
}

/* Style preset chips */
.style-row {
  gap: 8px !important;
}
.style-chip {
  background: var(--bg-1) !important;
  border: 1px solid var(--line) !important;
  color: var(--ink-0) !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  padding: 8px 16px !important;
  border-radius: 999px !important;
  height: auto !important;
  min-height: 0 !important;
}
.style-chip:hover {
  border-color: var(--ink-2) !important;
}
.style-chip.style-active {
  background: var(--ink-0) !important;
  color: var(--bg-0) !important;
  border-color: var(--ink-0) !important;
}

/* Example prompts */
.example-card {
  background: var(--bg-1) !important;
  border: 1px solid var(--line) !important;
  border-radius: 10px !important;
  padding: 12px 16px !important;
  font-size: 13px !important;
  color: var(--ink-0) !important;
  cursor: pointer !important;
  text-align: left !important;
  height: auto !important;
  min-height: 0 !important;
}
.example-card:hover {
  border-color: var(--accent) !important;
  color: var(--accent) !important;
}

/* The single primary action */
button.primary, .primary {
  background: var(--ink-0) !important;
  color: var(--bg-0) !important;
  border: none !important;
  border-radius: 999px !important;
  font-weight: 600 !important;
  font-size: 15px !important;
  padding: 14px 28px !important;
  height: auto !important;
  min-height: 0 !important;
  letter-spacing: 0.01em !important;
  box-shadow: var(--shadow) !important;
}
button.primary:hover {
  background: var(--ink-1) !important;
}

/* More options disclosure */
.disclosure summary {
  cursor: pointer !important;
  font-size: 13px !important;
  color: var(--ink-1) !important;
  padding: 8px 0 !important;
  list-style: none !important;
}
.disclosure summary::-webkit-details-marker { display: none; }
.disclosure summary::before {
  content: "▸ " !important;
  margin-right: 6px !important;
}
.disclosure[open] summary::before { content: "▾ " !important; }

/* Video result */
.video-frame {
  background: var(--bg-1) !important;
  border: 1px solid var(--line) !important;
  border-radius: 12px !important;
  padding: 16px !important;
  box-shadow: var(--shadow) !important;
}

/* Empty state */
.empty-state {
  text-align: center !important;
  padding: 64px 24px !important;
  color: var(--ink-1) !important;
  font-size: 14px !important;
  line-height: 1.6 !important;
}

/* Tabs */
.tabs > .tab-nav {
  background: transparent !important;
  border-bottom: 1px solid var(--line) !important;
  gap: 32px !important;
}
.tabs > .tab-nav > button {
  color: var(--ink-1) !important;
  font-size: 14px !important;
  font-weight: 500 !important;
  border-radius: 0 !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  padding: 12px 0 !important;
}
.tabs > .tab-nav > button.selected {
  color: var(--ink-0) !important;
  border-bottom-color: var(--ink-0) !important;
}

/* Dataframe */
table, .table-wrap {
  background: var(--bg-1) !important;
  border: 1px solid var(--line) !important;
  border-radius: 10px !important;
  font-size: 13px !important;
}

/* Sign-in panel (modal-feeling) */
.signin-panel {
  background: var(--bg-1) !important;
  border: 1px solid var(--line) !important;
  border-radius: 12px !important;
  padding: 24px !important;
  max-width: 380px !important;
  margin: 12px auto !important;
  box-shadow: var(--shadow) !important;
}
.signin-title {
  font-family: 'Source Serif 4', serif !important;
  font-size: 20px !important;
  font-weight: 600 !important;
  color: var(--ink-0) !important;
  margin: 0 0 4px 0 !important;
}
.signin-subtitle {
  font-size: 13px !important;
  color: var(--ink-1) !important;
  margin: 0 0 16px 0 !important;
}
.signin-row input {
  font-size: 14px !important;
  padding: 10px 14px !important;
  border-radius: 8px !important;
}
.signin-row button {
  font-size: 14px !important;
  padding: 10px 14px !important;
  border-radius: 8px !important;
}

/* Hide Gradio footer */
footer { display: none !important; }

/* Status line */
.signin-status {
  font-size: 13px !important;
  color: var(--good) !important;
  margin-top: 8px !important;
}
"""


# ---------- handlers --------------------------------------------------------

def build_gradio_app(launch: bool = True):
    import os
    L = os.environ.get("LTX_DEMO_LANG", "en")  # build-time default lang
    state = gr.State({"token": None, "lang": L, "me": None, "style": t("styles", L)[0], "mode": "text"})

    # ----- backend handlers ------------------------------------------------

    def login(user, pwd, state):
        c = _client(state)
        c.login(user, pwd)
        state["token"] = c.token
        try:
            state["me"] = c.me()
        except Exception:
            state["me"] = None
        me = state.get("me") or {}
        is_admin = me.get("role") == "admin"
        return (state,
                gr.update(visible=False),
                gr.update(value=t("signed_in_as", state["lang"], name=me.get("username", "user"))),
                gr.update(visible=is_admin))

    def signout(state):
        state["token"] = None
        state["me"] = None
        return state, gr.update(visible=True), gr.update(value="")

    def pick_style(style: str, state):
        state["style"] = style
        return state

    def pick_example(text: str, state):
        return text

    def refresh_models(state):
        c = _client(state)
        try:
            ids = [m["id"] for m in c.list_models() if m["enabled"]]
        except Exception:
            ids = []
        return gr.update(choices=ids)

    def refresh_history(state):
        c = _client(state)
        lang = state["lang"]
        try:
            rows = c.list_history(limit=20)
        except Exception:
            return [[t("library_empty", lang), "", "", "", ""]]
        if not rows:
            return [[t("library_empty", lang), "", "", "", ""]]
        return [[r["id"], r["kind"], r["model_id"], r["status"], r["created_at"]] for r in rows]

    def switch_mode(mode: str, state):
        state["mode"] = mode
        return (
            gr.update(visible=(mode == "text")),
            gr.update(visible=(mode == "image")),
        )

    def switch_lang(target: str, state):
        if state["lang"] == target:
            return state, gr.update(), gr.update(), gr.update()
        state["lang"] = target
        return (state,
                gr.update(elem_classes="lang-btn lang-active" if target == "en" else "lang-btn"),
                gr.update(elem_classes="lang-btn lang-active" if target == "zh" else "lang-btn"),
                gr.update(value=t("app_name", target)))

    def build_prompt(text: str, style: str, lang: str) -> str:
        if not text:
            return ""
        prefix = t("style_appended", lang, style=style) + ". "
        return prefix + text

    def map_duration(d: str) -> tuple[int, int]:
        # frames, height, width
        return {"short": (97, 384, 640), "medium": (161, 480, 768), "long": (241, 480, 768)}[d]

    def map_quality(q: str) -> int:
        return {"draft": 8, "standard": 20, "high": 40}[q]

    def map_size(s: str) -> tuple[int, int]:
        return {"small": (384, 640), "medium": (480, 768)}[s]

    def create_text(prompt_text, duration, quality, size, state, progress=gr.Progress()):
        lang = state["lang"]
        if not state.get("token"):
            raise gr.Error(t("err_no_login", lang))
        if not prompt_text or not prompt_text.strip():
            raise gr.Error(t("err_no_prompt", lang))
        c = _client(state)
        # ensure model list is loaded
        models = []
        try:
            models = [m["id"] for m in c.list_models() if m["enabled"]]
        except Exception:
            pass
        model_id = models[0] if models else "ltx-2b-distilled"
        full_prompt = build_prompt(prompt_text, state["style"], lang)
        frames, h, w = map_duration(duration)
        steps = map_quality(quality)
        # size override: short uses small res; otherwise map
        s_h, s_w = map_size(size)
        h, w = s_h, s_w
        def _cb(j):
            progress(j["progress"], desc=f'{t("creating", lang)} · {int(j["progress"]*100)}%')
        try:
            job_id = c.submit_t2v(model_id=model_id, prompt=full_prompt, num_frames=frames,
                                  height=h, width=w, num_inference_steps=steps,
                                  guidance_scale=5.0, fps=24)
            j = c.wait_job(job_id, on_progress=_cb)
            if j["status"] != "succeeded":
                raise gr.Error(j.get("error") or t("err_failed", lang))
            return c.result_url(job_id), job_id
        except Exception as e:
            raise gr.Error(str(e) or t("err_failed", lang))

    def create_image(img_path, prompt_text, strength, duration, quality, size, state, progress=gr.Progress()):
        lang = state["lang"]
        if not state.get("token"):
            raise gr.Error(t("err_no_login", lang))
        if not img_path:
            raise gr.Error(t("err_no_image", lang))
        c = _client(state)
        models = []
        try:
            models = [m["id"] for m in c.list_models() if m["enabled"]]
        except Exception:
            pass
        model_id = models[0] if models else "ltx-2b-distilled"
        upload_id = c.upload(img_path)
        full_prompt = build_prompt(prompt_text or "", state["style"], lang)
        frames, _, _ = map_duration(duration)
        steps = map_quality(quality)
        s_h, s_w = map_size(size)
        def _cb(j):
            progress(j["progress"], desc=f'{t("creating", lang)} · {int(j["progress"]*100)}%')
        try:
            job_id = c.submit_i2v(model_id=model_id, image_upload_id=upload_id, prompt=full_prompt,
                                  strength=float(strength), num_frames=frames,
                                  num_inference_steps=steps, guidance_scale=5.0, fps=24)
            j = c.wait_job(job_id, on_progress=_cb)
            if j["status"] != "succeeded":
                raise gr.Error(j.get("error") or t("err_failed", lang))
            return c.result_url(job_id), job_id
        except Exception as e:
            raise gr.Error(str(e) or t("err_failed", lang))

    def make_longer(last_job_id, state, progress=gr.Progress()):
        lang = state["lang"]
        if not state.get("token"):
            raise gr.Error(t("err_no_login", lang))
        if not last_job_id:
            raise gr.Error(t("err_no_prompt", lang))
        c = _client(state)
        models = [m["id"] for m in c.list_models() if m["enabled"]]
        model_id = next((m for m in models if "long" in m), models[0] if models else "ltx-2b-distilled")
        def _cb(j):
            progress(j["progress"], desc=f'{t("creating", lang)} · {int(j["progress"]*100)}%')
        try:
            job_id = c.submit_extend(parent_job_id=last_job_id, prompt="", num_frames=97,
                                     num_inference_steps=20, guidance_scale=5.0, fps=24)
            j = c.wait_job(job_id, on_progress=_cb)
            if j["status"] != "succeeded":
                raise gr.Error(j.get("error") or t("err_failed", lang))
            return c.result_url(job_id), job_id
        except Exception as e:
            raise gr.Error(str(e) or t("err_failed", lang))

    # ----- admin handlers --------------------------------------------------

    def refresh_admin_users(state):
        c = _client(state)
        try:
            users = c.admin_list_users()
            return [[u["id"], u["username"], u.get("email") or "",
                     u["role"], u["is_active"], u.get("last_login_at") or ""]
                    for u in users]
        except Exception as e:
            return [[f"error: {e}", "", "", "", "", ""]]

    def admin_add_user(username, email, password, role, state):
        lang = state["lang"]
        c = _client(state)
        try:
            u = c.admin_create_user(username, email or None, password, role)
            return (gr.update(value=f"✓ {u['username']} ({u['role']})"), refresh_admin_users(state))
        except Exception as e:
            return (gr.update(value=f"✗ {e}"), gr.update())

    def admin_reset_password(user_id, new_pw, state):
        lang = state["lang"]
        c = _client(state)
        try:
            c.admin_reset_password(int(user_id), new_pw)
            return gr.update(value="✓ password reset")
        except Exception as e:
            return gr.update(value=f"✗ {e}")

    def refresh_admin_models(state):
        c = _client(state)
        try:
            rows = c.admin_list_models()
            return [[m["id"], m["display_name"],
                     "✓" if m["downloaded"] else "—",
                     f"{m['size_gb']} GB" if m["downloaded"] else "—",
                     m["enabled"],
                     m["download_status"]["status"] if m.get("download_status") else ""]
                    for m in rows]
        except Exception as e:
            return [[f"error: {e}", "", "", "", "", ""]]

    def admin_download_model(model_id, state):
        c = _client(state)
        try:
            r = c.admin_download_model(model_id)
            return gr.update(value=f"started: {r.get('status')}")
        except Exception as e:
            return gr.update(value=f"✗ {e}")

    def refresh_admin_stats(state):
        c = _client(state)
        try:
            s = c.admin_stats()
            gpu = s["gpu"]
            d = s["disk"]
            users = s["users"]
            jobs = s["jobs"]
            pipe = s["pipeline"]
            recent = s["recent_jobs"]
            recent_md = "\n".join(
                f"- `{r['id']}` · {r['username']} · {r['kind']} · {r['status']} · {r['created_at'][:19] if r.get('created_at') else ''}"
                for r in recent
            ) or "(no jobs yet)"
            gpu_md = (f"**{gpu['name']}** · {gpu['vram_used_gb']} / {gpu['vram_total_gb']} GB"
                      if gpu["available"] else "CUDA not available")
            md = f"""### System

- **GPU:** {gpu_md}
- **Pipeline:** `{pipe['current_id']}`
- **Disk (data):** {d['data_free_gb']} / {d['data_total_gb']} GB free
- **Disk (models):** {d['model_free_gb']} / {d['model_total_gb']} GB free
- **Users:** {users['active']} active / {users['total']} total

### Jobs
- queued: **{jobs['queued']}**
- running: **{jobs['running']}**
- succeeded: **{jobs['succeeded']}**
- failed: **{jobs['failed']}**

### Recent activity (latest 20)

{recent_md}
"""
            return gr.update(value=md)
        except Exception as e:
            return gr.update(value=f"error: {e}")

    def signup_handler(username, email, password, state):
        lang = state["lang"]
        c = _client(state)
        try:
            c.signup(username, email, password)
            state["token"] = c.token
            state["me"] = c.me()
            return (state,
                    gr.update(visible=False),
                    gr.update(value=t("signed_in_as", lang, name=state["me"]["username"])),
                    gr.update(visible=state["me"]["role"] == "admin"))
        except Exception as e:
            return (state,
                    gr.update(),
                    gr.update(value=f"✗ {e}"),
                    gr.update())

    # ----- build blocks ----------------------------------------------------

    with gr.Blocks(title="LTX Studio", css=CSS, theme=gr.themes.Base()) as blocks:
        # Header
        with gr.Row(elem_classes="app-header"):
            with gr.Column(scale=8):
                gr.Markdown(
                    f'<span class="app-name"><span class="accent-dot"></span>{t("app_name", L)}</span>'
                )
            with gr.Column(scale=4):
                with gr.Row():
                    en_btn = gr.Button("English", elem_classes="lang-btn" + (" lang-active" if L == "en" else ""), scale=1)
                    zh_btn = gr.Button("中文", elem_classes="lang-btn" + (" lang-active" if L == "zh" else ""), scale=1)

        # Sign-in / sign-up panel (visible only when anonymous)
        with gr.Column(visible=True, elem_classes="signin-panel") as signin_panel:
            with gr.Tabs():
                with gr.Tab(t("signin_btn", L)):
                    gr.Markdown(f'<div class="signin-title">{t("signin_title", L)}</div>')
                    gr.Markdown(f'<div class="signin-subtitle">{t("signin_subtitle", L)}</div>')
                    with gr.Row(elem_classes="signin-row"):
                        u = gr.Textbox(label=t("username", L), placeholder="admin", scale=2)
                        p = gr.Textbox(label=t("password", L), type="password", scale=2)
                        btn = gr.Button(t("signin_btn", L), variant="primary", scale=1)
                    signin_status = gr.Markdown("")

                with gr.Tab(t("admin_signup_btn", L)):
                    gr.Markdown(f'<div class="signin-title">{t("admin_signup_title", L)}</div>')
                    gr.Markdown(f'<div class="signin-subtitle">{t("admin_signup_subtitle", L)}</div>')
                    with gr.Row(elem_classes="signin-row"):
                        su_username = gr.Textbox(label=t("username", L), scale=2)
                        su_email = gr.Textbox(label=t("admin_signup_email", L), scale=3)
                    with gr.Row(elem_classes="signin-row"):
                        su_password = gr.Textbox(label=t("admin_signup_password", L), type="password", scale=4)
                        signup_btn = gr.Button(t("admin_signup_btn", L), variant="primary", scale=1)
                    signup_status = gr.Markdown("")

        # Sign-in status banner (above tabs once logged in)
        signin_banner = gr.Markdown("", visible=False)

        # Tabs
        with gr.Tabs():
            # ----- Create tab -----
            with gr.Tab(t("tab_create", L)) as tab_create:
                # Hero
                gr.Markdown(f'<h1 class="hero-title">{t("hero_title", L)}</h1>')
                gr.Markdown(f'<p class="hero-subtitle">{t("hero_subtitle", L)}</p>')

                # Mode toggle: text vs image
                with gr.Row():
                    text_mode_btn = gr.Button(t("prompt_label", L), variant="primary", scale=1)
                    image_mode_btn = gr.Button(t("start_from_image", L), scale=1)

                # Text-mode panel
                with gr.Column(visible=True) as text_panel:
                    prompt_input = gr.Textbox(
                        label=t("prompt_label", L),
                        placeholder=t("prompt_placeholder", L),
                        lines=3,
                        elem_classes="big-prompt",
                    )
                    gr.Markdown(f'<div class="section-subtitle">{t("prompt_examples", L)}</div>')
                    with gr.Row():
                        ex1 = gr.Button(example_prompts(L)[0], elem_classes="example-card", scale=1)
                        ex2 = gr.Button(example_prompts(L)[1], elem_classes="example-card", scale=1)
                    with gr.Row():
                        ex3 = gr.Button(example_prompts(L)[2], elem_classes="example-card", scale=1)
                        ex4 = gr.Button(example_prompts(L)[3], elem_classes="example-card", scale=1)

                    # Style presets
                    gr.Markdown(f'<div class="section-subtitle">{t("style_label", L)}</div>')
                    with gr.Row(elem_classes="style-row"):
                        style_cine = gr.Button(t("styles", L)[0], elem_classes="style-chip style-active", scale=1)
                        style_anim = gr.Button(t("styles", L)[1], elem_classes="style-chip", scale=1)
                        style_real = gr.Button(t("styles", L)[2], elem_classes="style-chip", scale=1)
                        style_dream = gr.Button(t("styles", L)[3], elem_classes="style-chip", scale=1)

                    with gr.Row():
                        create_btn = gr.Button(t("create", L), variant="primary", scale=3)
                        make_longer_btn = gr.Button(t("make_longer", L), scale=1, visible=False)

                    # Result + last-job-id (hidden)
                    video_out = gr.Video(label=t("result_label", L), elem_classes="video-frame", visible=False)
                    last_job = gr.Textbox(visible=False)

                # Image-mode panel
                with gr.Column(visible=False) as image_panel:
                    img_input = gr.Image(type="filepath", label=t("image_upload", L))
                    img_prompt = gr.Textbox(
                        label=t("image_prompt_help", L),
                        placeholder=t("prompt_placeholder", L),
                        lines=2,
                        elem_classes="big-prompt",
                    )
                    img_strength = gr.Slider(0.0, 1.0, value=0.85, step=0.05, label=t("image_strength", L))
                    img_create_btn = gr.Button(t("create", L), variant="primary")
                    img_video_out = gr.Video(label=t("result_label", L), elem_classes="video-frame", visible=False)

                # Advanced options (collapsed by default)
                with gr.Accordion(t("more_options", L), open=False, elem_classes="disclosure") as advanced:
                    with gr.Row():
                        adv_duration = gr.Radio(
                            choices=[t("short", L), t("medium", L), t("long", L)],
                            value=t("medium", L),
                            label=t("duration_label", L),
                        )
                    with gr.Row():
                        adv_quality = gr.Radio(
                            choices=[t("draft", L), t("standard", L), t("high", L)],
                            value=t("standard", L),
                            label=t("quality_label", L),
                        )
                        adv_size = gr.Radio(
                            choices=[t("small", L), t("medium_res", L)],
                            value=t("medium_res", L),
                            label=t("size_label", L),
                        )

                gr.Markdown(f'<div class="section-subtitle" style="margin-top: 32px;">{t("powered_by", L)}</div>')

            # ----- Library tab -----
            with gr.Tab(t("tab_library", L)) as tab_library:
                gr.Markdown(f'<h2 class="section-title">{t("library", L)}</h2>')
                gr.Markdown(f'<div class="section-subtitle">{t("library_subtitle", L)}</div>')
                library_refresh = gr.Button(t("more_options", L))  # will repurpose as refresh
                library_table = gr.Dataframe(
                    headers=[t("job_col", L) if False else "id", "type", "model", "status", "created"],
                    interactive=False,
                )

                # ----- Admin tab (visible only for role=admin) -----
                with gr.Tab(t("tab_admin", L), visible=False) as tab_admin:
                    with gr.Tabs():
                        with gr.Tab(t("admin_users", L)):
                            gr.Markdown(f'<div class="section-subtitle">{t("admin_users_subtitle", L)}</div>')
                            users_table = gr.Dataframe(
                                headers=["id", "username", "email", "role", "active", "last login"],
                                interactive=False,
                            )
                            users_refresh_btn = gr.Button(t("admin_refresh", L))
                            with gr.Row():
                                admin_new_username = gr.Textbox(label=t("admin_username", L), scale=2)
                                admin_new_email = gr.Textbox(label=t("admin_email", L), scale=3)
                                admin_new_password = gr.Textbox(label=t("admin_password", L), type="password", scale=2)
                                admin_new_role = gr.Dropdown(
                                    choices=["user", "admin"], value="user",
                                    label=t("admin_role", L), scale=1,
                                )
                                admin_add_btn = gr.Button(t("admin_add_user", L), variant="primary", scale=1)
                            admin_add_status = gr.Markdown("")
                            with gr.Row():
                                admin_target_user_id = gr.Textbox(label=t("admin_user_id", L), scale=1)
                                admin_target_new_pw = gr.Textbox(label=t("admin_new_password", L), type="password", scale=3)
                                admin_reset_pw_btn = gr.Button(t("admin_reset_pw", L), scale=1)
                            admin_reset_status = gr.Markdown("")

                        with gr.Tab(t("admin_models", L)):
                            gr.Markdown(f'<div class="section-subtitle">{t("admin_models_subtitle", L)}</div>')
                            admin_models_table = gr.Dataframe(
                                headers=["id", "name", "downloaded", "size_gb", "enabled", "status"],
                                interactive=False,
                            )
                            admin_models_refresh_btn = gr.Button(t("admin_refresh", L))
                            with gr.Row():
                                admin_target_model_id = gr.Textbox(label="model id", scale=2)
                                admin_download_btn = gr.Button(t("admin_download", L), variant="primary", scale=1)
                            admin_download_status = gr.Markdown("")

                        with gr.Tab(t("admin_stats", L)):
                            gr.Markdown(f'<div class="section-subtitle">{t("admin_stats_subtitle", L)}</div>')
                            admin_stats_md = gr.Markdown("")
                            admin_stats_refresh_btn = gr.Button(t("admin_refresh", L))

                # ----- wiring (inside Blocks context) ----------------------------

                btn.click(login, [u, p, state], [state, signin_panel, signin_banner, tab_admin])
                signup_btn.click(signup_handler, [su_username, su_email, su_password, state],
                                 [state, signin_panel, signin_banner, tab_admin])

                en_btn.click(lambda s: switch_lang("en", s), [state], [state, en_btn, zh_btn, signin_panel])
                zh_btn.click(lambda s: switch_lang("zh", s), [state], [state, en_btn, zh_btn, signin_panel])

                text_mode_btn.click(lambda s: switch_mode("text", s), [state], [text_panel, image_panel])
                image_mode_btn.click(lambda s: switch_mode("image", s), [state], [text_panel, image_panel])

                ex1.click(lambda: example_prompts(L)[0], outputs=[prompt_input])
                ex2.click(lambda: example_prompts(L)[1], outputs=[prompt_input])
                ex3.click(lambda: example_prompts(L)[2], outputs=[prompt_input])
                ex4.click(lambda: example_prompts(L)[3], outputs=[prompt_input])

                style_cine.click(lambda s: pick_style(t("styles", s["lang"])[0], s), [state], [state])
                style_anim.click(lambda s: pick_style(t("styles", s["lang"])[1], s), [state], [state])
                style_real.click(lambda s: pick_style(t("styles", s["lang"])[2], s), [state], [state])
                style_dream.click(lambda s: pick_style(t("styles", s["lang"])[3], s), [state], [state])

                create_btn.click(create_text,
                                 [prompt_input, adv_duration, adv_quality, adv_size, state],
                                 [video_out, last_job]) \
                    .then(lambda v, j: (gr.update(value=v, visible=True), gr.update(visible=True), j),
                          [video_out, last_job], [video_out, make_longer_btn, last_job])

                img_create_btn.click(create_image,
                                     [img_input, img_prompt, img_strength, adv_duration, adv_quality, adv_size, state],
                                     [img_video_out, last_job]) \
                    .then(lambda v, j: (gr.update(value=v, visible=True), j),
                          [img_video_out, last_job], [img_video_out, last_job])

                make_longer_btn.click(make_longer, [last_job, state], [video_out, last_job]) \
                    .then(lambda v, j: (gr.update(value=v, visible=True), j),
                          [video_out, last_job], [video_out, last_job])

                library_refresh.click(refresh_history, [state], [library_table])

                # ----- admin wiring -----
                users_refresh_btn.click(refresh_admin_users, [state], [users_table])
                admin_add_btn.click(admin_add_user,
                                   [admin_new_username, admin_new_email, admin_new_password, admin_new_role, state],
                                   [admin_add_status, users_table])
                admin_reset_pw_btn.click(admin_reset_password,
                                         [admin_target_user_id, admin_target_new_pw, state],
                                         [admin_reset_status])
                admin_models_refresh_btn.click(refresh_admin_models, [state], [admin_models_table])
                admin_download_btn.click(admin_download_model, [admin_target_model_id, state],
                                         [admin_download_status])
                admin_stats_refresh_btn.click(refresh_admin_stats, [state], [admin_stats_md])

                # auto-refresh admin tables when Admin tab is selected (best-effort)
                tab_admin.select(refresh_admin_users, [state], [users_table], show_progress="hidden")

    port = get_settings().app_port_gradio
    if launch:
        blocks.launch(server_name="127.0.0.1", server_port=port, prevent_thread_lock=True)
    return blocks, port