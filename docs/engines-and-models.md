# Fairy — inference engines and models

Fairy talks to **any OpenAI-compatible chat endpoint** (`POST /v1/chat/completions`,
model auto-discovered via `GET /v1/models`). One flag points her at it:

    --strata-url http://host:port          # or config.json: {"strata": {"url": "..."}}

Hosted APIs need a key: set `FAIRY_API_KEY=*** in the environment.

**Degradation rule:** her "hands" (open_app / close_app / run_command /
open_hermes_session) are OpenAI-style function calls. If the engine or model
can't do tool calls, Fairy detects that and switches to chat-only mode by
herself. She always talks; the hands depend on the engine.

## Engines

| Engine | OS support | Hands (tool calls) | Start it | Point Fairy at |
|---|---|---|---|---|
| **llama.cpp `llama-server`** | Linux, Windows, macOS | yes (use `--jinja` so the chat template is correct) | `llama-server -m model.gguf --jinja --port 8080` | `--strata-url http://127.0.0.1:8080` |
| **Ollama** | Linux, Windows, macOS | only with tool-capable models (see list) | `ollama serve` (default port 11434) | `--strata-url http://127.0.0.1:11434` |
| **vLLM** | Linux (NVIDIA) | yes, if enabled at launch | `vllm serve Qwen/Qwen3-8B --enable-auto-tool-choice --tool-call-parser hermes` | `--strata-url http://127.0.0.1:8000/v1` |
| **LM Studio** | Windows, macOS, Linux | depends on the model's chat template | its built-in "Local Server" (port 1234) | `--strata-url http://127.0.0.1:1234/v1` |
| **Hosted: OpenAI, OpenRouter, etc.** | any | yes | set `FAIRY_API_KEY` | `--strata-url https://api.openai.com/v1` etc. |

Verified in this repo's development: llama.cpp-style endpoint serving a
**quantized Qwen3 GGUF** (iq3_xxs quant), hands fully working.
The other rows follow the same API contract but haven't been exercised here —
if one misbehaves on your box, open an issue and Fairy will adapt.

## Models that work well

What matters is **tool-calling ability** and speed (companion chat wants fast
answers). Quantizations (GGUF Q4/Q3/iq3) are fine — the reference build runs
one.

**Recommended (tool-capable, good at 4–14B):**
- **Qwen3 4B / 8B** (and their quants). In *non-thinking* mode they answer
  snappily; in thinking mode they must be given a large token budget (Fairy
  already allocates one, but very small `max_tokens` configs break them).
- **Nous Hermes 3 / Hermes 4** — explicitly fine-tuned for tool calling.
- **Llama 3.1 8B Instruct**
- **Mistral Nemo / Mistral Small**

**Chat-only fallback:** any instruction-tuned chat model. If it (or its
engine) can't do function calls, Fairy falls back automatically and stays a
conversation companion.

**Hardware rough guide:** 4–8B at Q4 runs on ~8 GB RAM; 14B wants ~16 GB+;
GPU inference makes her feel much more alive than CPU-only.

**Avoid for the hands:** tiny (<3B) models, aggressive quants of weak bases,
and reasoning models with too-small output budgets (the model spends every
token on internal reasoning and returns an empty message).

## No model at all?

    --brain stub

Canned replies — runs the whole UI, bubbles, tools-free. Good for trying
Fairy before installing an engine.
