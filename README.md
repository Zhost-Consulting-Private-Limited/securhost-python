# SecurHost Python SDK

Official Python SDK for the [SecurHost AI Gateway](https://securhost.com). Provides intelligent LLM routing, real-time voice sessions, autonomous job agents, custom personas, website chatbots, enterprise ERP connectors, automated failover, and cost telemetry.

[![Release](https://img.shields.io/github/v/release/Zhost-Consulting-Private-Limited/securhost-python?color=blue)](https://github.com/Zhost-Consulting-Private-Limited/securhost-python/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📦 Installation

### Direct Install via GitHub (Recommended)
```bash
pip install git+https://github.com/Zhost-Consulting-Private-Limited/securhost-python.git
```

### Install from PyPI
```bash
pip install securhost
```

---

## 🚀 Quickstart

```python
from securhost import SecurHostClient

# Zero URL configuration needed - defaults to https://securhost.com
client = SecurHostClient(api_key="nxs_live_...")

response = client.chat.complete(
    messages=[{"role": "user", "content": "Analyze customer support trends."}],
    model="gpt-4o",
    request_type="summarization",  # Enables smart cost routing
)

print("AI Response:", response.output_text)
print(f"Cost: ${response.cost.amount:.6f} | Saved: ${response.cost.saved:.6f} (Model served: {response.cost.model})")
```

### Async Client
```python
import asyncio
from securhost.aio import AsyncSecurHostClient

async def main():
    async with AsyncSecurHostClient(api_key="nxs_live_...") as client:
        reply = await client.chat.complete([{"role": "user", "content": "Hello"}])
        print(reply.output_text)

asyncio.run(main())
```

---

## 🎙️ Voice Agents & Real-Time Telephony
```python
# Create real-time voice streaming session
session = client.voice.create_session(
    persona_id=12,
    voice_id="alloy",
    model="gpt-4o-realtime",
    system_prompt="You are a helpful customer concierge."
)

# Outbound telephony AI call
call = client.voice.initiate_call(
    to_number="+14155552671",
    persona_id=12,
    prompt="Confirm scheduled reservation."
)
```

---

## 🤖 Autonomous Job Agents
```python
# Deploy background AI worker
agent = client.job_agents.create(
    name="Lead Researcher",
    role_brief={"objective": "Scrape and enrich qualified leads"},
    autonomy_level=1,
    daily_action_cap=100,
    sandbox=False,
    tools=["web_search", "crm_sync"]
)

# Emergency pause / resume
client.job_agents.pause(agent_id=agent["id"], reason="Maintenance window")
client.job_agents.resume(agent_id=agent["id"])
```

---

## 🛠️ Build & Publishing Guide

### Building Package Locally
```bash
python -m pip install --upgrade build twine
python -m build
```
This produces `dist/securhost-0.1.0-py3-none-any.whl` and `dist/securhost-0.1.0.tar.gz`.

### Publishing to PyPI
```bash
twine upload dist/*
```
*(Or configure `PYPI_API_TOKEN` secret in GitHub repository settings to publish automatically on release tag)*

---

## 📄 License
MIT License. Copyright (c) 2026 SecurHost.
