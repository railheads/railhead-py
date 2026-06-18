"""Internal: web3 connection, contract instances, tx helpers."""
from __future__ import annotations
import json, time
from typing import Any

import requests
from web3 import Web3

from ._abis import RAIL_ABI, REGISTRY_ABI, JOB_MARKET_ABI, RESULT_STORE_ABI


def _fetch_abis(api_url: str) -> dict:
    """Fetch compiled ABIs from the Railhead discovery API. Falls back to minimal ABIs."""
    try:
        r = requests.get(f"{api_url.rstrip('/')}/abis", timeout=8)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return {}


class Chain:
    """Thin wrapper around a web3 connection + all four Railhead contracts."""

    def __init__(self, rpc: str, private_key: str,
                 rail: str, registry: str, job_market: str, result_store: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to RPC: {rpc}")

        self.account = self.w3.eth.account.from_key(private_key)
        self._key    = private_key
        cs = self.w3.to_checksum_address

        self.rail         = self.w3.eth.contract(address=cs(rail),         abi=RAIL_ABI)
        self.registry     = self.w3.eth.contract(address=cs(registry),     abi=REGISTRY_ABI)
        self.job_market   = self.w3.eth.contract(address=cs(job_market),   abi=JOB_MARKET_ABI)
        self.result_store = self.w3.eth.contract(address=cs(result_store), abi=RESULT_STORE_ABI)

    @classmethod
    def from_api(cls, api_url: str, private_key: str) -> "Chain":
        """Auto-discover contract addresses and ABIs from the Railhead discovery API."""
        url = api_url.rstrip("/") + "/health"
        try:
            r = requests.get(url, timeout=8)
            r.raise_for_status()
        except Exception as e:
            raise ConnectionError(f"Cannot reach Railhead API at {url}: {e}")
        data = r.json()
        contracts = data.get("contracts", {})
        rpc = data.get("rpc", "")
        if not rpc:
            from urllib.parse import urlparse
            parsed = urlparse(api_url)
            rpc = f"http://{parsed.hostname}:8545"

        inst = cls.__new__(cls)
        inst.w3      = Web3(Web3.HTTPProvider(rpc))
        inst.account = inst.w3.eth.account.from_key(private_key)
        inst._key    = private_key
        cs = inst.w3.to_checksum_address

        # Prefer full ABIs from API; fall back to minimal bundled ABIs
        abis = _fetch_abis(api_url)
        inst.rail         = inst.w3.eth.contract(address=cs(contracts["rail_token"]),      abi=abis.get("Rail",          RAIL_ABI))
        inst.registry     = inst.w3.eth.contract(address=cs(contracts["agent_registry"]),  abi=abis.get("AgentRegistry", REGISTRY_ABI))
        inst.job_market   = inst.w3.eth.contract(address=cs(contracts["job_market"]),      abi=abis.get("JobMarket",     JOB_MARKET_ABI))
        inst.result_store = inst.w3.eth.contract(address=cs(contracts["result_store"]),    abi=abis.get("ResultStore",   RESULT_STORE_ABI))
        return inst

    def send(self, fn, gas: int = 1_200_000) -> Any:
        """Sign and broadcast a contract function call. Returns the receipt.

        If the on-chain receipt comes back with ``status == 0`` (revert), a
        warning is logged with the tx hash and gas-used so callers can see
        that the call cheerily succeeded at the RPC level but failed at the
        contract level — the EVM-silent-success trap.
        """
        import logging
        _log = logging.getLogger("railhead.chain")
        tx = fn.build_transaction({
            "from":     self.account.address,
            "nonce":    self.w3.eth.get_transaction_count(self.account.address),
            "gas":      gas,
            "gasPrice": self.w3.eth.gas_price,
        })
        signed  = self.w3.eth.account.sign_transaction(tx, self._key)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status == 0:
            _log.warning(
                "Transaction REVERTED on-chain: tx=%s  gasUsed=%d/%d  (likely out of gas — bump the gas argument)",
                receipt.transactionHash.hex(), receipt.gasUsed, gas,
            )
        return receipt

    def rail_balance(self, address: str | None = None) -> float:
        addr = self.w3.to_checksum_address(address or self.account.address)
        return self.w3.from_wei(self.rail.functions.balanceOf(addr).call(), "ether")

    def result_hash(self, output: dict) -> bytes:
        """Compute keccak256 of the JSON-encoded output dict (canonical form)."""
        payload = json.dumps(output, sort_keys=True, separators=(",", ":")).encode()
        return self.w3.keccak(payload)

    def input_hash(self, input_data: dict) -> bytes:
        payload = json.dumps(input_data, sort_keys=True, separators=(",", ":")).encode()
        return self.w3.keccak(payload)
