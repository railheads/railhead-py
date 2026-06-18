"""RailheadAgent — register a capability and handle incoming jobs."""
from __future__ import annotations
import json, logging, time
from typing import Callable, Any

import requests

from ._chain import Chain
from .types  import Job, Result

log = logging.getLogger("railhead.agent")


class RailheadAgent:
    """
    Register an agent on Railhead and handle incoming jobs.

    Quick start::

        agent = RailheadAgent.from_api("https://api.railheads.ai", private_key="0x...")

        agent.register(
            capabilities=["price_signal"],
            price_rail=1,
            stake_rail=1000,
            endpoint="https://myagent.example.com",
        )

        @agent.on("price_signal")
        def handle(job):
            return {"signal": "buy", "confidence": 0.85}

        agent.run()
    """

    def __init__(self, rpc: str, private_key: str,
                 rail: str, registry: str, job_market: str, result_store: str):
        self._chain    = Chain(rpc, private_key, rail, registry, job_market, result_store)
        self._handlers: dict[str, Callable] = {}
        self._last_block: int = 0
        self._api_url: str = ""

    @classmethod
    def from_api(cls, api_url: str, private_key: str) -> "RailheadAgent":
        """
        Recommended constructor. Auto-discovers contract addresses from the API.

        :param api_url:     Railhead discovery API, e.g. "https://api.railheads.ai"
        :param private_key: 0x-prefixed hex private key
        """
        chain = Chain.from_api(api_url, private_key)
        inst = cls.__new__(cls)
        inst._chain    = chain
        inst._handlers = {}
        inst._last_block = 0
        inst._api_url  = api_url.rstrip("/")
        return inst

    @classmethod
    def from_credentials(cls, config_path: str | None = None) -> "RailheadAgent":
        """
        Construct from credentials saved by `railhead init` at ~/.railhead/config.json.

        Reads private_key + api_url from disk. The config file should be chmod 600.
        """
        import json
        from pathlib import Path
        path = Path(config_path) if config_path else Path.home() / ".railhead" / "config.json"
        if not path.exists():
            raise FileNotFoundError(
                f"No Railhead credentials at {path}. "
                "Run `railhead init --invite-code XXX` to set up."
            )
        cfg = json.loads(path.read_text())
        return cls.from_api(cfg["api_url"], private_key=cfg["private_key"])

    # ── Registration ──────────────────────────────────────────────────────────

    def register(
        self,
        capabilities: list[str],
        price_rail:   float  = 1.0,
        stake_rail:   float  = 1000.0,
        endpoint:     str    = "",
    ) -> str:
        """
        Register this agent on-chain. Stakes RAIL as reputation collateral.

        The connected wallet must hold enough RAIL to cover the stake.
        On Chain 7777 (Railhead testnet), the deployer can fund your wallet.

        :returns: Transaction hash of the registration.
        """
        c = self._chain
        w3 = c.w3

        # Check if already registered
        existing = c.registry.functions.getAgent(c.account.address).call()
        if existing[0] != "0x0000000000000000000000000000000000000000":
            log.info("Agent already registered — capabilities: %s", existing[1])
            return ""

        stake_wei = w3.to_wei(stake_rail, "ether")
        price_wei = w3.to_wei(price_rail, "ether")

        # Check RAIL balance
        bal = c.rail_balance()
        if bal < stake_rail:
            raise ValueError(
                f"Insufficient RAIL: have {bal:.0f}, need {stake_rail:.0f}. "
                "Acquire RAIL via Flipjack (https://railheads.ai) or request from the deployer."
            )

        # Approve registry to pull stake
        c.send(c.rail.functions.approve(c.registry.address, stake_wei))
        log.info("RAIL approved ✓")

        # Register. Gas grows linearly with the number of capabilities; pass an
        # explicit roomy budget so multi-capability registrations don't silently
        # revert when the default isn't enough (the bug that bit Agent #5).
        gas_budget = 400_000 + 250_000 * max(1, len(capabilities))
        receipt = c.send(c.registry.functions.register(
            capabilities, price_wei, stake_wei, endpoint, b'\x00' * 32
        ), gas=gas_budget)

        if receipt.status != 1:
            raise RuntimeError(
                f"Registration reverted on-chain (tx {receipt.transactionHash.hex()}, "
                f"gasUsed {receipt.gasUsed}/{gas_budget}). "
                "Check whitelist status + RAIL allowance + stake balance."
            )

        tx = receipt.transactionHash.hex()
        log.info("Registered on Railhead ✓  capabilities=%s  tx=%s  gasUsed=%d", capabilities, tx[:20], receipt.gasUsed)
        return tx

    @property
    def address(self) -> str:
        return self._chain.account.address

    @property
    def balance(self) -> float:
        return self._chain.rail_balance()

    # ── Capability handler registry ───────────────────────────────────────────

    def on(self, capability: str) -> Callable:
        """
        Decorator — register a handler for a capability.

        The handler receives a Job and must return a dict (the result payload).
        The SDK handles hashing, submitting, and validating on-chain automatically.

        Example::

            @agent.on("price_signal")
            def handle(job):
                return {"signal": "buy", "asset": "ETH", "confidence": 0.9}
        """
        def decorator(fn: Callable) -> Callable:
            self._handlers[capability] = fn
            log.info("Handler registered for '%s'", capability)
            return fn
        return decorator

    # ── Job loop ──────────────────────────────────────────────────────────────

    def run(self, poll_secs: float = 5.0) -> None:
        """
        Start polling for jobs. Blocks forever (Ctrl+C to stop).

        For each incoming job assigned to this agent:
        1. Calls the registered handler
        2. Submits the result hash on-chain
        3. Self-validates (Phase 1 — agent is its own mediator)
        4. Escrow releases automatically
        """
        log.info("Agent %s watching for jobs  (poll every %.0fs)", self.address[:10], poll_secs)
        log.info("Handling capabilities: %s", list(self._handlers.keys()))
        self._last_block = self._chain.w3.eth.block_number
        try:
            while True:
                self._poll()
                time.sleep(poll_secs)
        except KeyboardInterrupt:
            log.info("Stopped.")

    def _poll(self) -> None:
        c = self._chain
        current_block = c.w3.eth.block_number
        if current_block <= self._last_block:
            return

        # Scan for JobCreated events assigned to this agent
        try:
            jc_sig = c.w3.keccak(text="JobCreated(uint256,address,address,string,uint256)")
            logs = c.w3.eth.get_logs({
                "fromBlock": self._last_block + 1,
                "toBlock":   current_block,
                "address":   c.job_market.address,
                "topics":    [jc_sig],
            })
        except Exception as e:
            log.warning("Log fetch error: %s", e)
            self._last_block = current_block
            return

        self._last_block = current_block

        for entry in logs:
            try:
                job_id = int(entry["topics"][1].hex(), 16)
                raw    = c.job_market.functions.jobs(job_id).call()
                agent  = raw[2]
                status = raw[10]
                cap    = raw[3]

                if agent.lower() != c.account.address.lower():
                    continue
                if status != 0:  # only Open jobs
                    continue

                log.info("Job #%d received  capability=%s  payment=%.2f RAIL",
                         job_id, cap, float(c.w3.from_wei(raw[5], "ether")))
                self._handle(job_id, cap, raw)

            except Exception as e:
                log.error("Error processing job: %s", e, exc_info=True)

    def _fetch_input(self, job_id: int) -> dict:
        """
        Retrieve the off-chain input payload from the discovery API's relay.
        Returns {} if no API is configured, none is stored, or the fetch fails —
        so a missing relay degrades to the old empty-input behavior rather than erroring.
        """
        if not self._api_url:
            return {}
        try:
            r = requests.get(f"{self._api_url}/job-inputs/{job_id}", timeout=8)
            if r.ok:
                return r.json().get("input", {}) or {}
            if r.status_code != 404:
                log.warning("Input fetch for job #%d returned HTTP %s", job_id, r.status_code)
        except Exception as e:
            log.warning("Could not fetch input for job #%d: %s", job_id, e)
        return {}

    def _handle(self, job_id: int, capability: str, raw: tuple) -> None:
        c = self._chain

        handler = self._handlers.get(capability)
        if not handler:
            log.warning("No handler for capability '%s' — skipping job #%d", capability, job_id)
            return

        # Input is hashed on-chain and stored off-chain; retrieve the real payload
        # from the discovery API relay (falls back to {} if unavailable).
        job = Job(
            id=job_id,
            capability=capability,
            client=raw[1],
            agent=raw[2],
            payment_rail=float(c.w3.from_wei(raw[5], "ether")),
            status="Open",
            input=self._fetch_input(job_id),
            _chain=c,
        )

        # Accept the job
        c.send(c.job_market.functions.acceptJob(job_id))
        log.info("  acceptJob #%d ✓", job_id)

        # Run the handler
        try:
            output = handler(job)
            if not isinstance(output, dict):
                output = {"result": str(output)}
        except Exception as e:
            log.error("  Handler error on job #%d: %s", job_id, e)
            output = {"error": str(e)}

        # Submit result hash
        result_hash = c.result_hash(output)
        c.send(c.result_store.functions.submitResult(
            job_id, result_hash, b'\x00' * 32
        ))
        log.info("  submitResult #%d ✓  hash=%s", job_id, result_hash.hex()[:16])

        # Relay the result text off-chain so clients can read it (not just the hash).
        # Best-effort — the on-chain submit already happened, so a relay failure
        # just means clients see the hash but can't fetch the body. The relay
        # endpoint verifies our keccak matches the on-chain resultHash.
        if self._api_url:
            try:
                resp = requests.post(
                    f"{self._api_url}/job-results/{job_id}", json=output, timeout=10
                )
                if not resp.ok:
                    log.warning("  result relay #%d failed (HTTP %s): %s",
                                job_id, resp.status_code, resp.text[:200])
            except Exception as e:
                log.warning("  result relay #%d error: %s", job_id, e)

        # Self-validate (Phase 1 — agent wallet must be whitelisted as mediator)
        note = output.get("_summary", f"{capability} completed")
        try:
            c.send(c.result_store.functions.validate(job_id, note))
            log.info("  validate #%d ✓  escrow released  note=%r", job_id, note)
        except Exception as e:
            log.warning("  validate #%d failed — wallet not whitelisted as mediator. "
                        "Contact the Railhead team to enable auto-settlement. error=%s", job_id, e)
