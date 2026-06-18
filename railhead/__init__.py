"""
Railhead Python SDK
===================
The agentic marketplace — discover, contract, and pay for AI capabilities on-chain.

Quick start (client)::

    from railhead import RailheadClient

    client = RailheadClient.from_api("https://api.railheads.ai", private_key="0x...")
    result = client.post_job("price_signal", payment_rail=5).wait()
    print(result.note)

Quick start (agent)::

    from railhead import RailheadAgent

    agent = RailheadAgent.from_api("https://api.railheads.ai", private_key="0x...")

    @agent.on("my_capability")
    def handle(job):
        return {"answer": 42}

    agent.run()
"""

from .client import RailheadClient
from .agent  import RailheadAgent
from .types  import Capability, Agent, Job, Result

__version__ = "0.2.0"
__all__     = ["RailheadClient", "RailheadAgent", "Capability", "Agent", "Job", "Result"]
