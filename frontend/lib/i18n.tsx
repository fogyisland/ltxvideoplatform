// lib/i18n.tsx — bilingual EN/中文 with a Context provider.
"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { Lang } from "./types";

type Dict = Record<string, string>;
const I18N: Record<Lang, Dict> = {
  en: {
    app_name: "LTX Studio",
    // navigation
    nav_create: "Create",
    nav_library: "Library",
    nav_admin: "Admin",
    nav_signout: "Sign out",
    // landing
    landing_title: "LTX Studio",
    landing_subtitle: "Generate short videos from text prompts — running on your own GPU.",
    landing_cta_signin: "Sign in",
    landing_cta_signup: "Create account",
    landing_hint: "Self-registration takes 30 seconds.",
    // auth
    signin: "Sign in",
    signin_title: "Welcome back",
    signin_subtitle: "Sign in to start creating",
    signup_title: "Create your account",
    signup_subtitle: "Sign up to start creating",
    username: "username",
    email: "email",
    password: "password (8+ chars)",
    signin_btn: "Sign in",
    signup_btn: "Create account",
    have_account: "Already have an account? Sign in",
    no_account: "New here? Create an account",
    err_signin_failed: "wrong username or password",
    err_signup_failed: "could not create account — username or email may be taken",
    // create page
    hero_create_title: "What do you want to create?",
    hero_create_subtitle: "Type a description, pick a style, and we'll make a short video.",
    prompt_label: "Describe your video",
    prompt_placeholder: "e.g. a cat playing piano in a jazz club",
    prompt_examples: "Need inspiration? Try one of these:",
    style_label: "Style",
    style_cinematic: "Cinematic",
    style_animated: "Animated",
    style_realistic: "Realistic",
    style_dreamy: "Dreamy",
    mode_text: "Describe your video",
    mode_image: "Start from an image",
    image_upload: "Choose a starting image",
    image_prompt_help: "What should happen in the video?",
    image_strength: "How much to change from the original",
    create_btn: "Create video",
    creating: "Creating your video",
    result_label: "Your video",
    make_longer: "Make it longer",
    more_options: "More options",
    duration_label: "Length",
    duration_short: "short · ~5s",
    duration_medium: "medium · ~10s",
    duration_long: "long · ~20s",
    quality_label: "Quality",
    quality_draft: "draft · fast",
    quality_standard: "standard",
    quality_high: "high · slow",
    size_label: "Size",
    size_small: "small · 480p",
    size_medium: "medium · 720p",
    prompt_long_help: "use `|` to split per window",
    tile_size: "tile size",
    overlap: "overlap",
    extra_frames: "extra frames",
    parent_job_id: "parent job id",
    extend_btn: "Extend",
    err_no_login: "Please sign in first.",
    err_no_prompt: "Please describe your video.",
    err_no_image: "Please choose a starting image.",
    err_failed: "Something went wrong. Try again.",
    powered_by: "powered by LTX-Video",
    // library
    library_title: "Library",
    library_subtitle: "Videos you've made before",
    library_empty: "Your creations will appear here. Make your first video to get started.",
    refresh: "Refresh",
    // admin
    admin_users: "Users",
    admin_models: "Models",
    admin_stats: "System",
    admin_users_sub: "Create accounts, reset passwords, enable or disable users",
    admin_models_sub: "Download and enable model variants",
    admin_stats_sub: "GPU, disk, queue and recent jobs",
    admin_add_user: "Add user",
    admin_user_id: "user id",
    admin_new_password: "new password",
    admin_reset_pw: "Reset password",
    admin_download: "Download",
    admin_id: "id",
    admin_username: "username",
    admin_email: "email",
    admin_role: "role",
    admin_active: "active",
    admin_last_login: "last login",
    admin_name: "name",
    admin_downloaded: "downloaded",
    admin_size: "size",
    admin_enabled: "enabled",
    admin_status: "status",
    admin_use_case: "use case",
    admin_disk_size: "disk",
    admin_vram: "VRAM",
    admin_download_progress: "downloading",
    admin_download_complete: "complete",
    admin_download_failed: "failed",
    admin_idle: "idle",
  },
  zh: {
    app_name: "LTX 工作室",
    nav_create: "创作",
    nav_library: "作品库",
    nav_admin: "管理",
    nav_signout: "退出",
    landing_title: "LTX 工作室",
    landing_subtitle: "用文字描述生成短视频 — 跑在你自己的 GPU 上。",
    landing_cta_signin: "登录",
    landing_cta_signup: "注册账号",
    landing_hint: "注册只需 30 秒。",
    signin: "登录",
    signin_title: "欢迎回来",
    signin_subtitle: "登录后即可开始创作",
    signup_title: "创建账号",
    signup_subtitle: "注册后即可开始创作",
    username: "用户名",
    email: "邮箱",
    password: "密码（至少 8 位）",
    signin_btn: "登录",
    signup_btn: "注册",
    have_account: "已有账号？登录",
    no_account: "新用户？创建账号",
    err_signin_failed: "用户名或密码错误",
    err_signup_failed: "无法创建账号 — 用户名或邮箱可能被占用",
    hero_create_title: "想创作什么？",
    hero_create_subtitle: "描述一下，选个风格，我们来生成短视频。",
    prompt_label: "描述你的视频",
    prompt_placeholder: "例如：一只猫在爵士酒吧弹钢琴",
    prompt_examples: "没灵感？试试这些：",
    style_label: "风格",
    style_cinematic: "电影感",
    style_animated: "动画",
    style_realistic: "写实",
    style_dreamy: "梦幻",
    mode_text: "描述你的视频",
    mode_image: "从图片开始",
    image_upload: "选择起始图片",
    image_prompt_help: "视频里应该发生什么？",
    image_strength: "相对原图的变化程度",
    create_btn: "生成视频",
    creating: "正在生成",
    result_label: "你的视频",
    make_longer: "延展时长",
    more_options: "更多选项",
    duration_label: "时长",
    duration_short: "短 · 约 5 秒",
    duration_medium: "中 · 约 10 秒",
    duration_long: "长 · 约 20 秒",
    quality_label: "画质",
    quality_draft: "草稿 · 快速",
    quality_standard: "标准",
    quality_high: "高清 · 慢",
    size_label: "尺寸",
    size_small: "小 · 480p",
    size_medium: "中 · 720p",
    prompt_long_help: "用 `|` 分隔不同镜头",
    tile_size: "窗口大小",
    overlap: "重叠帧数",
    extra_frames: "延展帧数",
    parent_job_id: "父任务 ID",
    extend_btn: "延展",
    err_no_login: "请先登录。",
    err_no_prompt: "请描述你的视频。",
    err_no_image: "请选择一张起始图片。",
    err_failed: "出错了，重试一下。",
    powered_by: "由 LTX-Video 提供算力",
    library_title: "作品库",
    library_subtitle: "你之前做过的视频",
    library_empty: "你的创作将出现在这里。先生成一条视频试试。",
    refresh: "刷新",
    admin_users: "用户",
    admin_models: "模型",
    admin_stats: "系统",
    admin_users_sub: "创建账号、重置密码、启用或禁用用户",
    admin_models_sub: "下载和启用模型变体",
    admin_stats_sub: "GPU、磁盘、队列和最近任务",
    admin_add_user: "添加用户",
    admin_user_id: "用户 ID",
    admin_new_password: "新密码",
    admin_reset_pw: "重置密码",
    admin_download: "下载",
    admin_id: "ID",
    admin_username: "用户名",
    admin_email: "邮箱",
    admin_role: "角色",
    admin_active: "启用",
    admin_last_login: "最近登录",
    admin_name: "名称",
    admin_downloaded: "已下载",
    admin_size: "大小",
    admin_enabled: "启用",
    admin_status: "状态",
    admin_use_case: "使用场景",
    admin_disk_size: "磁盘",
    admin_vram: "显存",
    admin_download_progress: "下载中",
    admin_download_complete: "完成",
    admin_download_failed: "失败",
    admin_idle: "空闲",
  },
};

const EXAMPLE_PROMPTS_EN = [
  "a cat playing piano in a jazz club",
  "aerial view of mountains at sunset",
  "a robot painting a self-portrait",
  "time-lapse of a flower blooming",
];
const EXAMPLE_PROMPTS_ZH = [
  "一只猫在爵士酒吧弹钢琴",
  "航拍山脉日落",
  "机器人在画自画像",
  "花朵绽放的延时摄影",
];

type Ctx = {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string) => string;
  examples: string[];
};

const I18nCtx = createContext<Ctx>({
  lang: "en",
  setLang: () => {},
  t: (k) => I18N.en[k] || k,
  examples: EXAMPLE_PROMPTS_EN,
});

const STORAGE_KEY = "ltx_lang";

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  useEffect(() => {
    const stored = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    if (stored === "en" || stored === "zh") setLangState(stored);
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, l);
  }, []);

  const t = useCallback((key: string) => I18N[lang][key] || I18N.en[key] || key, [lang]);
  const examples = lang === "zh" ? EXAMPLE_PROMPTS_ZH : EXAMPLE_PROMPTS_EN;
  return (
    <I18nCtx.Provider value={{ lang, setLang, t, examples }}>
      {children}
    </I18nCtx.Provider>
  );
}

export function useI18n(): Ctx {
  return useContext(I18nCtx);
}