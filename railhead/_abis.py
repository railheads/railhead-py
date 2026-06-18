# Minimal ABIs — only the functions the SDK calls.
# Keeping these inline means the SDK has no dependency on forge build output.

RAIL_ABI = [
    {"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
]

REGISTRY_ABI = [
    {"inputs":[{"name":"capabilities","type":"string[]"},{"name":"pricePerCall","type":"uint256"},{"name":"stake","type":"uint256"},{"name":"endpoint","type":"string"},{"name":"metadataHash","type":"bytes32"}],"name":"register","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"addr","type":"address"}],"name":"getAgent","outputs":[{"name":"","type":"tuple","components":[{"name":"agent","type":"address"},{"name":"capabilities","type":"string[]"},{"name":"pricePerCall","type":"uint256"},{"name":"stake","type":"uint256"},{"name":"status","type":"uint8"},{"name":"endpoint","type":"string"},{"name":"completedJobs","type":"uint256"},{"name":"disputedJobs","type":"uint256"},{"name":"registeredAt","type":"uint256"}]}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"getActiveAgents","outputs":[{"name":"","type":"address[]"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"addr","type":"address"},{"name":"authorized","type":"bool"}],"name":"setAgentWhitelist","outputs":[],"stateMutability":"nonpayable","type":"function"},
]

JOB_MARKET_ABI = [
    {"inputs":[{"name":"agent","type":"address"},{"name":"capability","type":"string"},{"name":"inputHash","type":"bytes32"},{"name":"payment","type":"uint256"},{"name":"deadline","type":"uint256"}],"name":"createJob","outputs":[{"name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"jobId","type":"uint256"}],"name":"acceptJob","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"","type":"uint256"}],"name":"jobs","outputs":[{"name":"id","type":"uint256"},{"name":"client","type":"address"},{"name":"agent","type":"address"},{"name":"capability","type":"string"},{"name":"inputHash","type":"bytes32"},{"name":"payment","type":"uint256"},{"name":"fee","type":"uint256"},{"name":"createdAt","type":"uint256"},{"name":"acceptedAt","type":"uint256"},{"name":"deadline","type":"uint256"},{"name":"status","type":"uint8"},{"name":"resultHash","type":"bytes32"},{"name":"disputeNote","type":"string"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"getOpenJobs","outputs":[{"name":"","type":"uint256[]"}],"stateMutability":"view","type":"function"},
    {"anonymous":False,"inputs":[{"indexed":True,"name":"jobId","type":"uint256"},{"indexed":True,"name":"client","type":"address"},{"indexed":True,"name":"agent","type":"address"},{"indexed":False,"name":"capability","type":"string"},{"indexed":False,"name":"payment","type":"uint256"}],"name":"JobCreated","type":"event"},
]

RESULT_STORE_ABI = [
    {"inputs":[{"name":"jobId","type":"uint256"},{"name":"resultHash","type":"bytes32"},{"name":"proofHash","type":"bytes32"}],"name":"submitResult","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"jobId","type":"uint256"},{"name":"note","type":"string"}],"name":"validate","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"","type":"uint256"}],"name":"results","outputs":[{"name":"jobId","type":"uint256"},{"name":"agent","type":"address"},{"name":"resultHash","type":"bytes32"},{"name":"inputHash","type":"bytes32"},{"name":"proofHash","type":"bytes32"},{"name":"committedAt","type":"uint256"},{"name":"validatedAt","type":"uint256"},{"name":"status","type":"uint8"},{"name":"mediator","type":"address"},{"name":"note","type":"string"}],"stateMutability":"view","type":"function"},
]
