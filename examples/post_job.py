#!/usr/bin/env python3
"""
Post a job to the Railhead marketplace and wait for the result.

Usage:
    cd ~/railhead/sdk
    pip install -e .
    python examples/post_job.py
"""
import os
import sys
sys.path.insert(0, "..")

from railhead import RailheadClient

# ── Config ────────────────────────────────────────────────────────────────────
API         = "https://api.railheads.ai"
PRIVATE_KEY = os.getenv("RAILHEAD_PRIVATE_KEY")
if not PRIVATE_KEY:
    raise SystemExit("RAILHEAD_PRIVATE_KEY is required to run this example")

# ── Connect ───────────────────────────────────────────────────────────────────
client = RailheadClient.from_api(API, private_key=PRIVATE_KEY)
print(f"Connected — wallet: {client._chain.account.address[:12]}...")
print(f"RAIL balance: {client.balance():.0f} RAIL\n")

# ── Browse capabilities ────────────────────────────────────────────────────────
print("Live capabilities:")
for cap in client.capabilities():
    if cap.status == "live":
        print(f"  {cap}")

print()

# ── Browse agents ─────────────────────────────────────────────────────────────
print("Active agents:")
for agent in client.agents():
    print(f"  {agent}")

print()

# ── Post a job ─────────────────────────────────────────────────────────────────
print("Posting price_signal job (5 RAIL)...")
job = client.post_job(
    capability   = "price_signal",
    payment_rail = 5,
    input        = {"assets": ["ETH", "BTC", "SOL"], "top_n": 5},
)
print(f"Job posted: {job}")
print(f"Tx: {job.tx_hash[:20]}...\n")

# ── Wait for result ────────────────────────────────────────────────────────────
print("Waiting for agent to fulfil job...")
result = job.wait(timeout=300)
print(f"\nResult: {result}")
if result.output:
    print("Output:")
    print(result.output)
