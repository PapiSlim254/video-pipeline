import os
import json
import requests

ACTIVE_PROVIDER = "groq"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "")

CLAUDE_MODEL = "claude-sonnet-4-6"
GROQ_MODEL   = "llama-3.3-70b-versatile"

def ask(system_prompt, user_prompt, expect_json=False):
    if ACTIVE_PROVIDER == "claude":
        return _ask_claude(system_prompt, user_prompt, expect_json)
    elif ACTIVE_PROVIDER == "groq":
        return _ask_groq(system_prompt, user_prompt, expect_json)
    else:
        raise ValueError(f"Unknown provider: {ACTIVE_PROVIDER}")

def ask_json(system_prompt, user_prompt):
    raw = ask(system_prompt, user_prompt, expect_json=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"AI response was not valid JSON.\nResponse: {raw}\nError: {e}")

def _ask_claude(system_prompt, user_prompt, expect_json):
    if not ANTHROPIC_API_KEY:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set.")
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    system = system_prompt
    if expect_json:
        system += "\n\nRespond with valid JSON only. No markdown, no explanation, no code fences."
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 1024,
        "system": system,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=30)
    if not response.ok:
        print(f"  [API Error] Status: {response.status_code}")
        print(f"  [API Error] Body: {response.text}")
    response.raise_for_status()
    return response.json()["content"][0]["text"].strip()

def _ask_groq(system_prompt, user_prompt, expect_json):
    if not GROQ_API_KEY:
        raise EnvironmentError("GROQ_API_KEY is not set.")
    system = system_prompt
    if expect_json:
        system += "\n\nRespond with valid JSON only. No markdown, no explanation, no code fences."
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens": 1024,
        "temperature": 0.7,
    }
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
    if not response.ok:
        print(f"  [API Error] Status: {response.status_code}")
        print(f"  [API Error] Body: {response.text}")
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()
