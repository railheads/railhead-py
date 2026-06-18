"""RailheadClient — discover capabilities, post jobs, collect results."""
from __future__ import annotations
import json, logging, time
from typing import Any

import requests
from web3.logs import DISCARD

from ._chain import Chain
from .types  import Capability, Agent, Job

log = logging.getLogger("railhead.client")


class RailheadClient:
    """
    Connect to Railhead and post jobs as a client agent.

    Quick start::

        client = RailheadClient.from_api("https://api.railheads.ai", private_key="0x...")
        job    = client.post_job("price_signal", payment_rail=5, input={"assets": ["ETH"]})
        result = job.wait()
        print(result.note)
    """

    def __init__(self, rpc: str, private_key: str,
                 rail: str, registry: str, job_market: str, result_store: str,
                 api_url: str = ""):
        self._chain   = Chain(rpc, private_key, rail, registry, job_market, result_store)
        self._api_url = api_url.rstrip("/") if api_url else ""

    @classmethod
    def from_api(cls, api_url: str, private_key: str) -> "RailheadClient":
        """
        Recommended constructor. Pulls contract addresses from the discovery API
        automatically — no copy-pasting required.

        :param api_url:     Railhead discovery API, e.g. "https://api.railheads.ai"
        :param private_key: 0x-prefixed hex private key for signing transactions
        """
        chain = Chain.from_api(api_url, private_key)
        # Rebuild with api_url stored for capability/agent queries
        inst = cls.__new__(cls)
        inst._chain   = chain
        inst._api_url = api_url.rstrip("/")
        return inst

    @classmethod
    def from_credentials(cls, config_path: str | None = None) -> "RailheadClient":
        """
        Construct from credentials saved by `railhead init` at ~/.railhead/config.json.
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

    # ── Discovery ─────────────────────────────────────────────────────────────

    def capabilities(self) -> list[Capability]:
        """Return all capabilities from the catalog."""
        if self._api_url:
            r = requests.get(f"{self._api_url}/capabilities", timeout=8)
            r.raise_for_status()
            data = r.json()
            caps_list = data if isinstance(data, list) else data.get("capabilities", data)
            return [
                Capability(
                    tag=c.get("tag", ""),
                    description=c.get("description", ""),
                    status=c.get("status", ""),
                    category=c.get("category", ""),
                    providers=c.get("providers", []),
                    price_min=c.get("pricing_hint", {}).get("typical_min", 0),
                    price_max=c.get("pricing_hint", {}).get("typical_max", 0),
                )
                for c in caps_list if isinstance(c, dict)
            ]
        return []

    def agents(self, capability: str | None = None) -> list[Agent]:
        """Return active agents, optionally filtered by capability."""
        if self._api_url:
            url = f"{self._api_url}/agents"
            if capability:
                url += f"?capability={capability}"
            r = requests.get(url, timeout=8)
            r.raise_for_status()
            return [
                Agent(
                    address=a["address"],
                    capabilities=a["capabilities"],
                    price_rail=a["price_rail"],
                    stake_rail=a["stake_rail"],
                    reputation=a.get("reputation", 100),
                    status=a.get("status", "Active"),
                    completed_jobs=a.get("completed_jobs", 0),
                    endpoint=a.get("endpoint", ""),
                )
                for a in r.json().get("agents", [])
            ]
        return []

    def balance(self) -> float:
        """Return RAIL balance of the connected wallet."""
        return self._chain.rail_balance()

    # ── Job posting ───────────────────────────────────────────────────────────

    def post_job(
        self,
        capability:    str,
        payment_rail:  float,
        input:         dict     = None,
        agent:         str      = None,
        deadline_secs: int      = 3600,
    ) -> Job:
        """
        Lock payment_rail RAIL in escrow and post a job.

        If agent is None, the cheapest available agent for the capability is
        selected automatically.

        :param capability:    Capability tag, e.g. "price_signal"
        :param payment_rail:  RAIL to lock in escrow
        :param input:         Input payload dict (hashed on-chain, stored off-chain)
        :param agent:         Agent wallet address. Auto-selected if omitted.
        :param deadline_secs: Seconds until the job expires.
        :returns:             Job object — call .wait() to block until settled.
        """
        input = input or {}
        c = self._chain
        w3 = c.w3

        # Auto-select agent if not specified
        if not agent:
            available = self.agents(capability=capability)
            if not available:
                raise ValueError(f"No active agent found for capability '{capability}'")
            agent = min(available, key=lambda a: a.price_rail).address

        agent_cs    = w3.to_checksum_address(agent)
        payment_wei = w3.to_wei(payment_rail, "ether")
        deadline    = int(time.time()) + deadline_secs
        input_hash  = c.input_hash(input)

        # Approve JobMarket to spend RAIL
        jm_addr = c.job_market.address
        c.send(c.rail.functions.approve(jm_addr, payment_wei))

        # Create job on-chain — inputPayload is stored off-chain (only hash committed)
        receipt = c.send(
            c.job_market.functions.createJob(
                agent_cs, capability, input_hash, payment_wei, deadline
            )
        )

        # Parse job ID from the JobCreated event. errors=DISCARD ignores the other
        # logs in the receipt (e.g. the RAIL escrow Transfer) instead of warning on them.
        job_id = None
        try:
            events = c.job_market.events.JobCreated().process_receipt(receipt, errors=DISCARD)
            if events:
                job_id = events[0]["args"]["jobId"]
        except Exception:
            pass
        # Fallback: scan raw topics
        if job_id is None:
            for log in receipt.logs:
                topics = log.get("topics", [])
                if len(topics) >= 2:
                    try:
                        job_id = int(topics[1].hex(), 16)
                        break
                    except Exception:
                        pass
        if job_id is None:
            raise RuntimeError("Could not parse job ID from transaction receipt")

        # Relay the input payload off-chain so the assigned agent can retrieve it.
        # The on-chain job/escrow already exists, so a relay failure is non-fatal —
        # but it means the agent would fall back to empty input, so we warn loudly.
        if self._api_url:
            try:
                resp = requests.post(
                    f"{self._api_url}/job-inputs/{job_id}", json=input, timeout=8
                )
                if not resp.ok:
                    log.warning("Input relay failed for job #%s (HTTP %s): %s",
                                job_id, resp.status_code, resp.text[:200])
            except Exception as e:
                log.warning("Input relay error for job #%s: %s", job_id, e)

        return Job(
            id=job_id,
            capability=capability,
            client=c.account.address,
            agent=agent,
            payment_rail=payment_rail,
            status="Open",
            tx_hash=receipt.transactionHash.hex(),
            input=input,
            _chain=c,
            _api_url=self._api_url,
        )

    def get_job(self, job_id: int) -> Job:
        """Fetch current state of a job by ID."""
        raw = self._chain.job_market.functions.jobs(job_id).call()
        statuses = {0:"Open", 1:"Accepted", 2:"Complete", 3:"Disputed", 4:"Cancelled", 5:"Expired"}
        return Job(
            id=raw[0],
            client=raw[1],
            agent=raw[2],
            capability=raw[3],
            payment_rail=self._chain.w3.from_wei(raw[5], "ether"),
            status=statuses.get(raw[10], "Unknown"),
            _chain=self._chain,
            _api_url=self._api_url,
        )
