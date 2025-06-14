# A Decentralized Research Trend Finder (draft)

**This project was completed as the Final Project for ‘Generative AI and Blockchain 2025’ at GIST, supervised by Professor Heung-No Lee.**


### Author

1️⃣ **Minjun Song** from EECS, GIST

2️⃣ **Junsung Kim** from EECS, GIST

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

* Build a marketplace where agents can **autonomously request and fulfil AI tasks**  
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

1. No open workflow that allows agents to commission, pay for and deliver AI work without relying on centralized APIs or custodial wallets  
2. ERC-20 payments incur high gas costs or batching overhead, so they are inappropriate for “pay-per-request” AI.  
3. Traditional AI SaaS logs user data on vendor servers, so it provides weak data protection safeguards.

Our prototype solved above problems by:

* **Executable A2A handshake** (request → invoice → payment → fulfilment)  
* **On-chain escrow** on the WorldLand network for a transparent settlement  
* **All prompts & artefacts stay inside each agent** (never stored on a central backend)

---

### ✅ Claims and Achievements
<!-- have to check this part (1, )/ -->
1. **Tri-party agent stack** — `UserAgent`, `BillingAgent`, `ResearchAgent` each run an `A2AStarletteApplication`, talking only via JSON  
2. **On-chain billing flow** — `BillingAgent` issues an invoice, checks the `paidContent()` function in the Solidity contract, then forwards the task  
3. **End-to-end autonomy** — `UserAgent` polls, signs, sends, waits for the receipt and resumes processing with zero human intervention  
4. **Research-trend discovery** — `ResearchAgent` pulls ≤10 recent arXiv papers, summarises abstracts and synthesises trends via Gemini-2.5-flash  
5. **Stateless, decentralised deployment** — no shared DB or orchestrator; each agent can run anywhere

---

### 🧠 AI Methods Used
<!-- have to check these parts with demo (LLM-powered Trend Analysis, Agent Autonomy layer) -->
- **LLM-powered Trend Analysis**: Gemini-2.5-flash model creates search terms, summaries and a markdown “Recent Trend Analysis” section for the user. 
- **Paper Retrieval Tool**: the custom search_papers() helper leverages the arXiv API and filters the top-10 most relevant results for the past year. 
- **Agent Autonomy Layer**: every request/response is serialised into Part objects, converted to Google Generative AI types.Part when calling the LLM, and back again, enabling model calls to be slotted seamlessly into the A2A pipeline.

---

### 🧪 Experimental Results

<!--
We ran several experiments where queries were submitted on various academic topics. Example results:

| Topic             | No. of Papers Retrieved  | Summary Length | Time to Completion | Payment (WLC) |
|-------------------|--------------------------|----------------|--------------------|---------------|
| RAG               | 10                       | ~400 words     | ~40 seconds        | 0.0002        |
| AI Safety         | 10                       | ~300 words     | ~40 seconds        | 0             |
| Blockchain Scaling| 10                       | ~350 words     | ~40 seconds        | 0             |

All responses included readable, coherent summaries with citations where relevant. The Ethereum testnet was used for transactions, and all payments were successfully verified via smart contract before proceeding with inference.
-->

---

### 🎥 Demo Video
<!-- 

🔗 attach demo video here (GIF) 
-->

---

### 🚀 How to Run

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
├── .env
├── BillingContract.sol
├── README.md
├── billing_agent
│   ├── __main__.py
│   ├── agent_executor.py
│   └── contract_abi.json
├── client.py
├── requirement.txt
├── research_agent
│   ├── __main__.py
│   ├── agent_executor.py
│   └── utils.py
├── run
│   ├── start_billing.sh
│   ├── start_research.sh
│   └── start_user.sh
└── user_agent
    ├── __main__.py
    └── agent_executor.py
```

---

### 📌 Summary
<!-- 

This project brings together generative AI and decentralized finance through a novel A2A protocol. It validates the viability of autonomous AI agents performing economic transactions and delivering value in a decentralized network. Our modular design allows easy scalability and customization to support a wide array of agent-based AI services in a Web3 ecosystem. 
-->

---

### 📬 Contact

For more information, please contact:

📧 paulmjsong@gm.gist.ac.kr

📧 wnstjd123@gm.gist.ac.kr
