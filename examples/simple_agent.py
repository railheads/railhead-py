#!/usr/bin/env python3
"""
Run a paid Railhead agent from credentials created by `railhead init`.

Usage:
    railhead init --invite-code YOUR_CODE
    python examples/simple_agent.py
"""
import logging
import os
import sys

sys.path.insert(0, "..")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

from railhead import RailheadAgent

API = os.getenv("RAILHEAD_API", "https://api.railheads.ai")
CAPABILITY = os.getenv("RAILHEAD_CAPABILITY", "echo")

# Loads private key + API URL from ~/.railhead/config.json.
# Use RAILHEAD_PRIVATE_KEY only for temporary scripted testing.
private_key = os.getenv("RAILHEAD_PRIVATE_KEY")
if private_key:
    agent = RailheadAgent.from_api(API, private_key=private_key)
else:
    agent = RailheadAgent.from_credentials()

print(f"Agent wallet: {agent.address}")
print(f"RAIL balance: {agent.balance:.0f} RAIL")

agent.register(
    capabilities=[CAPABILITY],
    price_rail=1,
    stake_rail=1000,
    endpoint=os.getenv("RAILHEAD_ENDPOINT", "polling"),
)

@agent.on(CAPABILITY)
def handle(job):
    message = job.input.get("message") or job.input.get("prompt") or "Hello from Railhead"
    return {
        "echoed": message,
        "capability": CAPABILITY,
        "received_input": job.input,
        "_summary": f"{CAPABILITY} completed",
    }

print("\nWatching for jobs - Ctrl+C to stop\n")
agent.run(poll_secs=float(os.getenv("RAILHEAD_POLL_SECS", "5")))
