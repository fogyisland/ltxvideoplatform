# LTX-Video setup notes (Windows, RTX 4060 8GB, Aug 2026)

## What we learned

The LTX-Video `0.9.8` checkpoint (`ltxv-2b-0.9.8-distilled.safetensors`, ~6 GB)
is a single safetensors file. **It is NOT loadable via `diffusers.from_pretrained`
or a Hugging Face repo name** — it's loaded directly with
`LTXVideoPipeline.from_pretrained(path)` using the official `ltx_video` package
(https://github.com/Lightricks/LTX-Video), which reads the pipeline config from
the safetensors' metadata field.

## The pipeline needs three things, all from the LTX-Video repo

```
models/
├── ltxv-2b-0.9.8-distilled.safetensors     # the weights (6 GB)
├── ltxv-spatial-upscaler-0.9.8.safetensors # optional, for multi-scale (500 MB)
├── text_encoder/                            # PixArt T5-XXL (17 GB merged)
│   ├── config.json
│   ├── model.safetensors                     # T5-XXL weights, single file
│   ├── pytorch_model.bin → model.safetensors # symlink (transformers 4.x
│   │                                        #   T5 looks for pytorch_model.bin)
│   ├── text_encoder/                         # subdir matched by subfolder="text_encoder"
│   │   ├── config.json
│   │   ├── model.safetensors → ../model.safetensors
│   │   └── pytorch_model.bin → ../model.safetensors
│   └── tokenizer/                            # T5 tokenizer
│       ├── added_tokens.json
│       ├── special_tokens_map.json
│       ├── spiece.model
│       └── tokenizer_config.json
```

Why the double-nested `text_encoder/text_encoder/`: the official LTX-Video
inference calls `T5EncoderModel.from_pretrained(text_encoder_model_name_or_path,
subfolder="text_encoder")` — i.e., `text_encoder_path/text_encoder/`. The
PythArt-XL repo on HF (`PixArt-alpha/PixArt-XL-2-1024-MS`) already has the
double nesting, so following the same convention makes the code work for both
local and HF-cloud cases.

## Why the symlinks

`transformers>=4.40` (and 4.57.6 in particular) only checks
`pytorch_model.bin` for T5 weights — NOT `model.safetensors`. The T5
config also has the same behavior. So we symlink
`pytorch_model.bin → model.safetensors` to satisfy both Transformers
legacy code paths and the safetensors-native paths.

**Critical Windows note**: `os.path.isfile()` on Windows does NOT follow
symlinks (this is a known Python-on-Windows quirk). We must use real copies
or hardlinks, not symlinks, when the consumer uses `os.path.isfile` (which
Transformers' `_get_resolved_checkpoint_files` does).

## VRAM reality (RTX 4060 8GB)

The 2B distilled model needs **~15 GB** in bfloat16 to load:
- T5-XXL encoder: ~9.5 GB
- Transformer: ~4.5 GB
- VAE: ~1 GB

8 GB is insufficient. Inference even starts (1 step worked in our test) but
crashes with `RuntimeError: mat1 is on cuda:0, different from other tensors
on cpu` because the `offload_to_cpu` flag is partial.

**To run on 8 GB you need**:
- 4-bit T5 (`T5EncoderModel.from_pretrained(..., load_in_4bit=True)`)
- or `accelerate.dispatch_model` for layer-by-layer CPU offload
- or a smaller text encoder (e.g. a distilled T5)

**To run comfortably, get a 12 GB+ GPU** (RTX 3060 12GB, RTX 4070, etc.).

## Download commands

```bash
# Pipeline weights + spatial upscaler
HF_ENDPOINT=https://hf-mirror.com python -c "
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
from huggingface_hub import hf_hub_download
for fn in ['ltxv-2b-0.9.8-distilled.safetensors',
           'ltxv-spatial-upscaler-0.9.8.safetensors']:
    hf_hub_download(repo_id='Lightricks/LTX-Video', filename=fn, local_dir='./models')
"

# T5-XXL text encoder (17 GB sharded) — download and merge to a single file
HF_ENDPOINT=https://hf-mirror.com python -c "
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
from huggingface_hub import hf_hub_download
for fn in ['text_encoder/model-00001-of-00002.safetensors',
           'text_encoder/model-00002-of-00002.safetensors']:
    hf_hub_download(repo_id='PixArt-alpha/PixArt-XL-2-1024-MS', filename=fn, local_dir='./models/text_encoder.tmp')
# then merge to ./models/text_encoder/model.safetensors
"

# T5 tokenizer
HF_ENDPOINT=https://hf-mirror.com python -c "
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
from huggingface_hub import hf_hub_download
for fn in ['tokenizer/added_tokens.json', 'tokenizer/special_tokens_map.json',
           'tokenizer/spiece.model', 'tokenizer/tokenizer_config.json']:
    hf_hub_download(repo_id='PixArt-alpha/PixArt-XL-2-1024-MS', filename=fn, local_dir='./models/text_encoder')
"
```

## Install the ltx_video Python package

```bash
# github.com is unreachable from this machine; use a mirror
git clone --depth=1 https://ghfast.top/https://github.com/Lightricks/LTX-Video.git /tmp/LTX-Video
pip install -e /tmp/LTX-Video --no-deps
```

Or just run `python scripts/install_ltx_video.py`.
