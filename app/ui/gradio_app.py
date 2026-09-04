# app/ui/gradio_app.py
from __future__ import annotations
import gradio as gr

from app.config import get_settings
from app.ui.api_client import ApiClient


def _client(state) -> ApiClient:
    base = f"http://127.0.0.1:{get_settings().app_port_api}"
    return ApiClient(base, token=state.get("token"))


def build_gradio_app(launch: bool = True):
    state = gr.State({"token": None})

    def login(user, pwd, state):
        c = _client(state)
        c.login(user, pwd)
        state["token"] = c.token
        return state, f"logged in as {c.me()['username']}"

    def do_t2v(model_id, prompt, steps, frames, h, w, state, progress=gr.Progress()):
        c = _client(state)
        def _cb(j):
            progress(j["progress"], desc=f"{j['stage']} ({j['status']})")
        job_id = c.submit_t2v(model_id=model_id, prompt=prompt, num_frames=int(frames),
                              height=int(h), width=int(w),
                              num_inference_steps=int(steps), guidance_scale=5.0, fps=24)
        j = c.wait_job(job_id, on_progress=_cb)
        if j["status"] != "succeeded":
            raise gr.Error(j.get("error") or j["status"])
        return c.result_url(job_id)

    def do_i2v(model_id, img_path, prompt, strength, steps, frames, state, progress=gr.Progress()):
        c = _client(state)
        upload_id = c.upload(img_path)
        def _cb(j):
            progress(j["progress"], desc=f"{j['stage']} ({j['status']})")
        job_id = c.submit_i2v(model_id=model_id, image_upload_id=upload_id, prompt=prompt,
                              strength=float(strength), num_frames=int(frames),
                              num_inference_steps=int(steps), guidance_scale=5.0, fps=24)
        j = c.wait_job(job_id, on_progress=_cb)
        if j["status"] != "succeeded":
            raise gr.Error(j.get("error") or j["status"])
        return c.result_url(job_id)

    def do_extend(parent_job_id, prompt, steps, frames, state, progress=gr.Progress()):
        c = _client(state)
        def _cb(j):
            progress(j["progress"], desc=f"{j['stage']} ({j['status']})")
        job_id = c.submit_extend(parent_job_id=parent_job_id, prompt=prompt,
                                 num_frames=int(frames),
                                 num_inference_steps=int(steps), guidance_scale=5.0, fps=24)
        j = c.wait_job(job_id, on_progress=_cb)
        if j["status"] != "succeeded":
            raise gr.Error(j.get("error") or j["status"])
        return c.result_url(job_id)

    def do_long_video(model_id, prompt, steps, frames, tile_size, overlap, state, progress=gr.Progress()):
        c = _client(state)
        def _cb(j):
            progress(j["progress"], desc=f"{j['stage']} ({j['status']})")
        job_id = c.submit_long_video(model_id=model_id, prompt=prompt, num_frames=int(frames),
                                     height=480, width=768,
                                     num_inference_steps=int(steps), guidance_scale=5.0, fps=24,
                                     temporal_tile_size=int(tile_size),
                                     temporal_overlap=int(overlap))
        j = c.wait_job(job_id, on_progress=_cb)
        if j["status"] != "succeeded":
            raise gr.Error(j.get("error") or j["status"])
        return c.result_url(job_id)

    def refresh_models(state):
        c = _client(state)
        ids = [m["id"] for m in c.list_models() if m["enabled"]]
        return gr.update(choices=ids)

    def refresh_history(state, limit=20):
        c = _client(state)
        rows = c.list_history(limit=limit)
        return [[r["id"], r["kind"], r["model_id"], r["status"], r["created_at"]] for r in rows]

    with gr.Blocks(title="LTX-Video Web Platform") as blocks:
        gr.Markdown("# LTX-Video")

        with gr.Row():
            u = gr.Textbox(label="username")
            p = gr.Textbox(label="password", type="password")
            btn = gr.Button("Login")
            status = gr.Markdown()

        with gr.Tabs():
            with gr.Tab("Generate — T2V"):
                with gr.Row():
                    mp = gr.Dropdown(label="model", choices=[], interactive=True)
                    refresh_btn = gr.Button("Refresh models")
                prompt = gr.Textbox(label="prompt")
                with gr.Row():
                    steps = gr.Slider(1, 100, value=20, step=1, label="steps")
                    frames = gr.Slider(9, 241, value=121, step=8, label="frames (8n+1)")
                    h = gr.Slider(64, 1024, value=480, step=32, label="height (÷32)")
                    w = gr.Slider(64, 1024, value=768, step=32, label="width (÷32)")
                run = gr.Button("Generate", variant="primary")
                video = gr.Video()
                refresh_btn.click(refresh_models, [state], [mp])
                run.click(do_t2v, [mp, prompt, steps, frames, h, w, state], [video])

            with gr.Tab("Generate — I2V"):
                with gr.Row():
                    imp = gr.Dropdown(label="model", choices=[], interactive=True)
                    irefresh = gr.Button("Refresh models")
                img = gr.Image(type="filepath")
                iprompt = gr.Textbox(label="prompt")
                with gr.Row():
                    istrength = gr.Slider(0.0, 1.0, value=0.85, step=0.05, label="strength")
                    isteps = gr.Slider(1, 100, value=20, step=1, label="steps")
                    iframes = gr.Slider(9, 241, value=121, step=8, label="frames (8n+1)")
                irun = gr.Button("Generate", variant="primary")
                ivideo = gr.Video()
                irefresh.click(refresh_models, [state], [imp])
                irun.click(do_i2v, [imp, img, iprompt, istrength, isteps, iframes, state], [ivideo])

            with gr.Tab("Generate — Long-video"):
                lmp = gr.Dropdown(label="model (long-multishot)", choices=[], interactive=True)
                lrefresh = gr.Button("Refresh models")
                lprompt = gr.Textbox(label="prompts (use | to split windows)")
                with gr.Row():
                    ltile = gr.Slider(40, 161, value=80, step=1, label="tile_size")
                    loverlap = gr.Slider(8, 80, value=24, step=1, label="overlap")
                    lframes = gr.Slider(81, 241, value=161, step=8, label="frames (8n+1)")
                    lsteps = gr.Slider(1, 100, value=30, step=1, label="steps")
                lrun = gr.Button("Generate", variant="primary")
                lvideo = gr.Video()
                lrefresh.click(refresh_models, [state], [lmp])
                lrun.click(do_long_video, [lmp, lprompt, lsteps, lframes, ltile, loverlap, state], [lvideo])

            with gr.Tab("Generate — Extend (last-frame)"):
                ep = gr.Textbox(label="parent job_id")
                eprompt = gr.Textbox(label="prompt (optional)")
                with gr.Row():
                    esteps = gr.Slider(1, 100, value=20, step=1, label="steps")
                    eframes = gr.Slider(9, 241, value=121, step=8, label="extra frames")
                erun = gr.Button("Extend", variant="primary")
                evideo = gr.Video()
                erun.click(do_extend, [ep, eprompt, esteps, eframes, state], [evideo])

            with gr.Tab("Models"):
                gr.Markdown("List at `GET /api/v1/models`. Click *Refresh models* in Generate tabs to populate dropdowns.")
                refresh_all = gr.Button("List enabled models")
                model_list = gr.Dataframe(headers=["id", "display_name", "vram_gb", "enabled"], interactive=False)
                def _list(state):
                    c = _client(state)
                    return [[m["id"], m["display_name"], m["vram_gb"], m["enabled"]] for m in c.list_models()]
                refresh_all.click(_list, [state], [model_list])

            with gr.Tab("History"):
                history_refresh = gr.Button("Refresh")
                history_table = gr.Dataframe(headers=["id", "kind", "model_id", "status", "created_at"], interactive=False)
                history_refresh.click(refresh_history, [state], [history_table])

            with gr.Tab("Account"):
                me_btn = gr.Button("Who am I?")
                me_out = gr.Markdown()
                def _me(state):
                    c = _client(state)
                    u = c.me()
                    return f"id={u['id']}  username={u['username']}  role={u['role']}"
                me_btn.click(_me, [state], [me_out])

        btn.click(login, [u, p, state], [state, status])

    port = get_settings().app_port_gradio
    if launch:
        blocks.launch(server_name="0.0.0.0", server_port=port, prevent_thread_lock=True)
    return blocks, port
