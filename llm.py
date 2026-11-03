# Talks to whichever AI provider the user has a key for.
# Most providers accept OpenAI-style requests at their own web address,
# so one OpenAI client works for all of them; only the address and model change.

import json, os, re
from getpass import getpass

from dotenv import load_dotenv, set_key
from openai import OpenAI
from pydantic import ValidationError

ENV_FILE = ".env"

# name -> web address, key prefixes used to guess the provider, and an
# optional default model. Providers without a default ask the user to pick one.
PROVIDERS = {
    "openai":     {"label": "OpenAI",     "base_url": "https://api.openai.com/v1/",                               "prefixes": ["sk-proj-", "sk-"], "env": "OPENAI_API_KEY"},
    "gemini":     {"label": "Google Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "prefixes": ["AIza"], "env": "GEMINI_API_KEY", "default_model": "gemini-3.8-flash"},
    "anthropic":  {"label": "Anthropic Claude", "base_url": "https://api.anthropic.com/v1/",                       "prefixes": ["sk-ant-"], "env": "ANTHROPIC_API_KEY"},
    "openrouter": {"label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1/",                             "prefixes": ["sk-or-"], "env": "OPENROUTER_API_KEY"},
    "groq":       {"label": "Groq",       "base_url": "https://api.groq.com/openai/v1/",                           "prefixes": ["gsk_"], "env": "GROQ_API_KEY"},
    "xai":        {"label": "xAI Grok",   "base_url": "https://api.x.ai/v1/",                                      "prefixes": ["xai-"], "env": "XAI_API_KEY"},
    "mistral":    {"label": "Mistral",    "base_url": "https://api.mistral.ai/v1/",                                "prefixes": [], "env": "MISTRAL_API_KEY"},
    "deepseek":   {"label": "DeepSeek",   "base_url": "https://api.deepseek.com/v1/",                              "prefixes": [], "env": "DEEPSEEK_API_KEY"},
    "ollama":     {"label": "Ollama (local, no key)", "base_url": "http://localhost:11434/v1/",                    "prefixes": [], "env": None, "no_key": True},
}


class LLMError(Exception):
    pass


# Guesses the provider from how the key starts, e.g. "sk-ant-" -> anthropic.
# Longer prefixes are checked first so "sk-ant-" wins over OpenAI's "sk-".
def guessProvider(key):
    matches = [
        (len(prefix), name)
        for name, p in PROVIDERS.items()
        for prefix in p["prefixes"]
        if key.startswith(prefix)
    ]
    return max(matches)[1] if matches else None


# Reads settings from .env. Returns None for anything not set.
# Also accepts provider-specific names like GEMINI_API_KEY, so older setups keep working.
def loadSettings():
    load_dotenv(ENV_FILE)
    key = os.getenv("LLM_API_KEY")
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower() or None

    if not key:
        for name, p in PROVIDERS.items():
            if p["env"] and os.getenv(p["env"]):
                key = os.getenv(p["env"])
                provider = provider or name
                break

    if key and not provider:
        provider = guessProvider(key)

    if provider and provider not in PROVIDERS and not os.getenv("LLM_BASE_URL"):
        raise LLMError(f"Unknown LLM_PROVIDER '{provider}'. Use one of: {', '.join(PROVIDERS)}, or set LLM_BASE_URL.")

    info = PROVIDERS.get(provider, {})
    return {
        "provider": provider,
        "key": key or ("ollama" if info.get("no_key") else None),
        "base_url": os.getenv("LLM_BASE_URL") or info.get("base_url"),
        "model": os.getenv("LLM_MODEL") or info.get("default_model"),
    }


def isReady(settings):
    return bool(settings["key"] and settings["base_url"] and settings["model"])


def makeClient(settings):
    return OpenAI(api_key=settings["key"], base_url=settings["base_url"])


def _pick(options, label):
    for i, opt in enumerate(options, start=1):
        print(f"  {i}. {opt}")
    while True:
        answer = input(f"Pick a {label} (1-{len(options)}): ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1]
        print("Not a valid choice, try again.")


# Asks the provider which models this key can use, then lets the user choose.
# Falls back to typing a model name if the provider can't list them.
def chooseModel(settings):
    try:
        # Gemini lists models as "models/<name>"; requests only need the name
        names = sorted(m.id.removeprefix("models/") for m in makeClient(settings).models.list())
    except Exception:
        names = []

    if names:
        print(f"\nThis key can use {len(names)} models.")
        if len(names) <= 30:
            for i, n in enumerate(names, start=1):
                print(f"  {i}. {n}")
        else:
            print("  (too many to list; type part of a name to search)")
        while True:
            answer = input("Type a number, a model name, or part of one to search: ").strip()
            if answer.isdigit() and len(names) <= 30 and 1 <= int(answer) <= len(names):
                return names[int(answer) - 1]
            if answer in names:
                return answer
            found = [n for n in names if answer.lower() in n.lower()]
            if len(found) == 1:
                return found[0]
            if found:
                print("Matches: " + ", ".join(found[:25]) + (" ..." if len(found) > 25 else ""))
            else:
                print("No model matches that.")

    print("\nCouldn't get a model list from this provider. Check its website for model names.")
    while True:
        name = input("Model name: ").strip()
        if name:
            return name


# First-run setup: asks for a key, guesses the provider, picks a model,
# and saves everything to .env (which git ignores, so keys never reach GitHub).
def setup():
    print("\n=== AI provider setup ===")
    print("Paste an API key from any supported provider. It's saved only in your local .env file.")
    print("(For Ollama on your own computer, just press Enter.)")
    key = getpass("API key (hidden as you type): ").strip()

    if key:
        provider = guessProvider(key)
        if provider:
            label = PROVIDERS[provider]["label"]
            if input(f"That looks like a key for {label}. Correct? [Y/n]: ").strip().lower() in ("n", "no"):
                provider = None
    else:
        provider = "ollama"

    base_url = None
    if not provider:
        labels = {PROVIDERS[n]["label"]: n for n in PROVIDERS}
        labels["Other (I have its web address)"] = "other"
        print("\nWhich provider is this key for?")
        provider = labels[_pick(list(labels), "provider")]
        if provider == "other":
            base_url = input("Provider's OpenAI-compatible base URL (e.g. https://example.com/v1): ").strip()
            provider = "custom"

    info = PROVIDERS.get(provider, {})
    settings = {
        "provider": provider,
        "key": key or "ollama",
        "base_url": base_url or info.get("base_url"),
        "model": info.get("default_model"),
    }
    if settings["model"]:
        if input(f"Use the default model '{settings['model']}'? [Y/n]: ").strip().lower() in ("n", "no"):
            settings["model"] = chooseModel(settings)
    else:
        settings["model"] = chooseModel(settings)

    if not os.path.exists(ENV_FILE):
        open(ENV_FILE, "w").close()
    set_key(ENV_FILE, "LLM_API_KEY", settings["key"], quote_mode="never")
    set_key(ENV_FILE, "LLM_PROVIDER", provider, quote_mode="never")
    set_key(ENV_FILE, "LLM_MODEL", settings["model"], quote_mode="never")
    if base_url:
        set_key(ENV_FILE, "LLM_BASE_URL", base_url, quote_mode="never")
    os.environ.update({"LLM_API_KEY": settings["key"], "LLM_PROVIDER": provider, "LLM_MODEL": settings["model"]})
    if base_url:
        os.environ["LLM_BASE_URL"] = base_url

    print(f"Saved. Using {info.get('label', provider)} with model {settings['model']}.\n")
    return settings


# Loads saved settings, running setup first if anything is missing.
def getSettings(force_setup=False):
    settings = None if force_setup else loadSettings()
    if settings is None or not isReady(settings):
        settings = setup()
    return settings


# Pulls the JSON object out of a reply, even if the model wrapped it
# in ```json fences or added a sentence before it.
def _extractJson(text):
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in the reply")
    return json.loads(text[start:end + 1])


# Asks the model a question and returns its answer as an instance of `schema`
# (a pydantic class). Works with any provider: instead of relying on
# provider-specific structured output, it asks for JSON and checks it,
# retrying once with the error if the reply doesn't fit.
def askJson(settings, system, user, schema, temperature=None):
    client = makeClient(settings)
    instructions = (
        "\n\nReply with only a JSON object (no other text) matching this JSON schema:\n"
        + json.dumps(schema.model_json_schema())
    )
    messages = [
        {"role": "system", "content": system + instructions},
        {"role": "user", "content": user},
    ]
    extra = {} if temperature is None else {"temperature": temperature}

    last_error = None
    for _ in range(2):
        try:
            response = client.chat.completions.create(model=settings["model"], messages=messages, **extra)
        except Exception as e:
            raise LLMError(_friendlyError(e, settings)) from e

        reply = response.choices[0].message.content
        try:
            return schema.model_validate(_extractJson(reply))
        except (ValueError, ValidationError) as e:
            last_error = e
            messages.append({"role": "assistant", "content": reply or ""})
            messages.append({"role": "user", "content": f"That reply wasn't valid ({e}). Reply again with only the JSON object."})

    raise LLMError(f"The model didn't return a usable answer: {last_error}")


def _friendlyError(e, settings):
    status = getattr(e, "status_code", None)
    # some providers (e.g. Gemini) report a bad key as a 400 error
    if status in (401, 403) or (status == 400 and "api key" in str(e).lower()):
        return "The API key was rejected. Run with --setup to enter a new key."
    if status == 404:
        return f"Model '{settings['model']}' wasn't found at this provider. Run with --setup to pick another."
    if status == 429:
        return "Rate limit or quota reached for this key. Wait a bit or check your provider's billing page."
    if status and status >= 500:
        return "The AI provider is busy or having problems right now. Try again in a minute."
    if settings.get("provider") == "ollama":
        return "Couldn't reach Ollama. Make sure it's running on this computer."
    return f"The AI request failed: {e}"
