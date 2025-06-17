# Web3 AI Marketplace: Agent Interaction And Payment Via Smart Contracts (draft)

**This project was completed as the Final Project for ‘Generative AI and Blockchain 2025’ at GIST, supervised by Professor Heung-No Lee.**


### Author

1️⃣ **Minjun Song** from Electrical Engineering and Computer Science (EECS), Gwangju Institute of Science and Technology (GIST)

2️⃣ **Junsung Kim** from Electrical Engineering and Computer Science (EECS), Gwangju Institute of Science and Technology (GIST)

---

### Class Detail

This class focuses on the intgration of blockchain and generative AI, exploring how these two technologies can interact and complement each other.  
* **Blockchain** After focusing on the 2008 financial crisis, Bretton-Woods breakdown, and the end of the gold standard, the class studies Bitcoin (white paper + fundamentals), Ethereum (white paper + smart-contract patterns such as ERC-20, NFTs and stablecoins), and WorldLand. Students also examine monetary-policy debates such as Triffin dilemma, Hayek’s “private money,” and Trump-era trade-policy papers to understand how crypto may redistribute wealth and reshape global finance.
* **Generative-AI** Based on Transformer architecture theory, this class cover LLaMA, DeepSeek, and practical acceleration techniques (LoRA fine-tuning, decentralized/federated training).

---

### 📖 Project Overview

This repository presents a proof-of-concept digital marketplace in which autonomous agents collaborate and exchange AI services by means of an Agent-to-Agent (A2A) protocol and EVM smart-contract payments.

Inspired by **LiberVance MyAI Network**, the system features:

* Decentralized interaction between **user-owned** and **service-provider-owned** AI agents  
* Privacy-respecting design (no central logging of prompts or outputs)
* Real-time, trust-less payments via on-chain escrow  
* Task delegation and fulfillment entirely managed by agents

---

### 🎯 Objectives

* Build a marketplace where agents can **autonomously request and fulfill AI tasks**  
* Enable **peer-to-peer transactions** through a smart contract  
* Guarantee **privacy** by never uploading user data to a central server  
* Prototype a coherent pipeline that integrates agent communication, blockchain payments, and AI inference tasks

---

### 📌 Scope

This project is a **minimum viable product (MVP)** focused on a research-trend discovery service, but the architecture is extendable to a wide range of AI services. It currently demonstrates:

* **A2A interaction** between user-owned and provider-owned agents  
* **Blockchain-based billing & payment confirmation** for full transparency  
* **On-demand AI services** searching papers via arXiv API and generating trend analysis with Gemini  
* **Gradio-based UI** for easy access

---

### ❓ Problem Definition

Web3 promises user sovereignty and decentralization, but autonomous **AI-to-AI commerce** still lacks a shared framework. Specifically:

* No open workflow that allows agents to commission, pay for and deliver AI work without relying on centralized APIs or custodial wallets  
* ERC-20 payments incur high gas costs or batching overhead, so they are inappropriate for “pay-per-request” AI.  
* Traditional AI SaaS logs user data on vendor servers, so it provides weak data protection safeguards.

Our prototype solved above problems by:

* **Executable A2A handshake** (request → invoice → payment → fulfillment)  
* **On-chain escrow** on the WorldLand network for a transparent settlement  
* **All prompts & artefacts stay inside each agent** (never stored on a central backend)

---

### ✅ Claims & Achievements
* **Tri-party agent architecture** — `UserAgent`, `BillingAgent`, `ResearchAgent` each run independently and talk only through the A2A JSON protocol  
* **On-chain billing flow** — `BillingAgent` issues an invoice, verifies payment through Solidity contract's `paidContent()` function, then forwards the task  
* **End-to-end autonomy** — The `UserAgent` signs and sends the WLC (Web3 Lightweight Contract) payment, while the `BillingAgent` autonomously polls the blockchain for settlement. Once settlement is detected, it proceeds to resume downstream processing, all without human intervention  

---

### 🧠 AI Methods Used
- **LLM-powered Trend Analysis**: Gemini-2.5-flash model creates search terms, summaries and a markdown “Recent Trend Analysis” section for the user. 
- **Paper Retrieval Tool**: the custom search_papers() helper leverages the arXiv API and filters the top-10 most relevant results for the past year. 
- **Agent Autonomy Layer**: every request/response is serialised into Part objects, converted to Google Generative AI types.Part when calling the LLM, and back again, enabling model calls to be slotted seamlessly into the A2A pipeline.

---

### 🌐 Open-source Code

| Library | License Type | Notes |
| --------------------------- | ---------------- | --------------------------------------- |
| `a2a-sdk` | MIT (on GitHub) | Agent-to-agent communication lib |
| `aiohttp`, `aiofiles` | Apache 2.0 / MIT | Async networking / file I/O |
| `fastapi`, `starlette` | MIT | Web framework / ASGI toolkit |
| `gradio`, `gradio_client` | Apache 2.0 | UI interface for ML apps |
| `pydantic`, `pydantic_core` | MIT | Data validation |
| `requests`, `httpx` | Apache 2.0 / BSD | HTTP client libraries |
| `google-*` packages | Apache 2.0 | Google Cloud APIs, maintained by Google |
| `protobuf`, `grpcio` | BSD / Apache 2.0 | Protocol buffers and gRPC |
| `eth-*`, `web3` | MIT | Ethereum interaction libraries |
| `uvicorn` | BSD | ASGI server |
| `SQLAlchemy` | MIT | SQL ORM |
| `numpy`, `pandas` | BSD | Scientific computing / data analysis |
| `orjson` | Apache 2.0 | High-performance JSON parsing |
| `Authlib` | BSD | OAuth and JWT handling |
| `huggingface-hub` | Apache 2.0 | HuggingFace's model API client |

---

### 🧪 Experimental Results

1. **Experimental Environment**

| Item               | Details                                                                                             |
|--------------------|-----------------------------------------------------------------------------------------------------|
| **HW**             | Apple M2 Pro (16 GB RAM)                                                                            |
| **OS / Kernel**    | macOS Sequoia 15.5                                                                                  |
| **Python**         | 3.12.7 (`venv`)                                                                                     |
| **Core Libraries** | FastAPI 0.111 · Uvicorn 0.30 · SQLModel 0.0.16                                                      |
| **Smart Contract** | Deployed on the WorldLand mainnet (contract address: 0x98003661dDe56E8A4D47CC0a92Fae65d65f375c6)    |
| **Agents**         | `billing`, `research`, `user`                                                                       |
| **Network**        | Same-host loopback (127.0.0.1)                                                                      |

> **Note** Ports are fixed to `billing:10000`, `research:10001`, and `user:10002` for this experiment.  



2. **Scenario Definition**

- **Submit Query.** The browser UI (left pane) sends a `POST /query` request with JSON body `{ "query": "VQA" }` to the **User Agent**.  
- **Payment Phase.** The User Agent calls the **Billing Agent**, which signs and broadcasts a smart-contract transaction.  
- **Research Phase.** After the payment-confirmed event is received, the **Billing Agent** invokes the **Research Agent**, which crawls 10 papers and generates an LLM-based summary and research trends.  
- **Return & Display.** The **Research Agent** returns the summaries and trends to the **User Agent** via the **Billing Agent**; the results are displayed in the browser UI.  
 
---

### 🎥 Demo Video
[![Demo Video](https://img.youtube.com/vi/7P3vQ9LGHOw/0.jpg)](https://www.youtube.com/watch?v=7P3vQ9LGHOw)

Please click the picture above to watch this video

---

### 🚀 How To Run

1. **Clone the repository:**
   ```bash
   git clone https://github.com/paulmjsong/BCAI_A2A.git
   cd BCAI_A2A
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirement.txt
   ```

3. **Configure your WorldLand wallet and environment:**
   - Deploy the smart contract using the provided **BillingContract.sol**.
   - Add your metamask wallet private key, contract address, and Gemini api key in .env

4. **Start Billing Agent and Research Agent:**
   ```bash
   source run/start_billing.sh
   source run/start_research.sh
   ```

5. **Start User Agent and run the Gradio interface for the User Agent:**
   ```bash
   source run/start_user.sh
   python3 client.py
   ```

6. **Interaction** 
   Enter a query and receive the summarised trends.

---

### 📚 File Structure
```bash
BCAI_A2A
├── A2A demo.mp4
├── billing_agent
│   ├── __main__.py
│   ├── agent_executor.py
│   └── contract_abi.json
├── BillingContract.sol
├── chat_logs (experimental results)
│   └── 20250616_94cbc6477bb853a57ec020c6877a8d9ff7bb4a348d8ce5eb8e5c5e29286905ea.json
├── client.py
├── LICENSE
├── README.md
├── requirement.txt
├── research_agent
│   ├── __main__.py
│   ├── agent_executor.py
│   └── utils.py
├── run
│   ├── start_billing.sh
│   ├── start_research.sh
│   └── start_user.sh
└── user_agent
    ├── __main__.py
    └── agent_executor.py
```

---

### 📌 Summary

This MVP demonstrates that fully autonomous, agent-to-agent (A2A) commerce is practical today with only Python services and a single Solidity contract. Three independent agents—UserAgent, BillingAgent, and ResearchAgent - issue an on-chain invoice, verify a WLC payment, and return an LLM-generated research-trend report without any human intervention or shared database.

The prototype proves five key claims:

>* **Tri-party agent architecture**  
>* **On-chain billing flow**  
>* **End-to-end autonomy**  
>* **Research-trend discovery**  
>* **Stateless, decentralised deployment**

In local tests the full round-trip—from query submission to Markdown result—completes in under 40 s per request on the WorldLand mainnet.

---

### 📬 Contact

For more information, please contact:

📧 paulmjsong@gm.gist.ac.kr

📧 wnstjd123@gm.gist.ac.kr
