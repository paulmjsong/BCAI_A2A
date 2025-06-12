# [Project Title Placeholder]

**This project was completed as the Final Project for ‘Generative AI and Blockchain 2025’ at GIST, supervised by Professor Heung-No Lee.**

---

## 📌 Project Title
**[Insert Project Title Here]**  
_A Decentralized Agent-to-Agent (A2A) Protocol-Driven AI Marketplace on Blockchain_

---

## 📖 Project Overview

This project demonstrates a proof-of-concept digital marketplace utilizing A2A protocol where autonomous agents collaborate and exchange services using smart contracts on the blockchain. The system implements a decentralized interaction between user-owned and service-provider-owned AI agents with privacy-respecting mechanisms, real-time payments, and task delegation. It draws inspiration from the **MyAI Network**—a Web3 AI framework proposed by **LiberVance** for decentralized AI model ownership.

---

## 🎯 Objectives

- To implement a digital service marketplace where agents can autonomously request and fulfill AI tasks.
- To enable peer-to-peer microtransactions using Ethereum smart contracts.
- To ensure a privacy-preserving architecture where user data and queries are not centrally logged.
- To experiment with the integration of agent communication, blockchain payments, and AI inference tasks in a coherent pipeline.

---

## 📌 Scope

This project is a minimum viable prototype (MVP) focusing on a research paper summarization service, but the architecture is extendable to various AI services. Currently, it demonstrates:

- **Agent-to-Agent (A2A)** interaction protocol.
- **Blockchain-based billing** and payment confirmation.
- **On-demand AI services**, e.g., research summarization via arXiv API.
- **User interface built with Gradio** for ease of access.

---

## ❓ Problem Definition

While Web3 infrastructures offer user sovereignty and decentralization, there is no standardized protocol for AI agents to interact, transact, and commission tasks among each other autonomously. Current models either rely on centralized APIs or suffer from inefficient micropayment handling. This project solves this gap by:

- Introducing a working A2A interaction pattern,
- Utilizing smart contracts for trustless payments,
- Ensuring that individual users retain control over their data and agents.

---

## ✅ Claims and Achievements

1. **Implemented a full-stack A2A protocol-based system with real smart contract integration.**
2. **Enabled autonomous inter-agent task delegation and execution via Ethereum smart contracts.**
3. **Demonstrated effective summarization of academic research papers via external API calls (arXiv).**
4. **Showcased a user-friendly interface for initiating and monitoring AI services.**
5. **Maintained a fully decentralized architecture where service-providing agents are independently deployed.**

---

## 🧠 AI Methods Used

- **Text Summarization**: Keyword-guided summary generation using a fine-tuned transformer-based LLM.
- **Research Retrieval**: Integration with the arXiv API for up-to-date academic literature on user-defined topics.
- **Agent Autonomy**: Agents operate independently and communicate via structured JSON messages over the A2A protocol.

---

## 🧪 Experimental Results

We ran several experiments where queries were submitted on various academic topics. Example results:

| Topic             | No. of Papers Retrieved | Summary Length | Time to Completion | Payment (ETH) |
|-------------------|--------------------------|----------------|---------------------|---------------|
| RAG               | 7                        | ~400 words     | ~12 seconds         | 0.0002        |
| AI Safety         | 5                        | ~300 words     | ~10 seconds         | 0.00015       |
| Blockchain Scaling| 6                      | ~350 words     | ~11 seconds         | 0.00018       |

All responses included readable, coherent summaries with citations where relevant. The Ethereum testnet was used for transactions, and all payments were successfully verified via smart contract before proceeding with inference.

---

## 🎥 Demo Video

[![Watch Demo](https://img.youtube.com/vi/your_video_id_here/0.jpg)](https://www.youtube.com/watch?v=your_video_id_here)  
🔗 [Watch Full Demo on YouTube](https://www.youtube.com/watch?v=your_video_id_here)

---

## 🚀 How to Run

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/yourrepo.git
   cd yourrepo```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt```
3. **Configure your WorldLand wallet and environment:**
   - Add your private key and Google AI API in .env.
   - Deploy the billing smart contract using the provided script.
4. **Run the Gradio interface for the User Agent:**
   ```bash
   python client.py```
5. **Start Billing Agent and Research Agent:**
   ```bash
   source run/start_1
   source run/start_2
   source run/start_3```
6. **Use the Gradio UI** to input a query, make the payment (on Ethereum testnet), and receive summarized research.

---

## 📚 File Structure

---

## 📌 Summary

This project brings together generative AI and decentralized finance through a novel A2A protocol. It validates the viability of autonomous AI agents performing economic transactions and delivering value in a decentralized network. Our modular design allows easy scalability and customization to support a wide array of agent-based AI services in a Web3 ecosystem.

---

## 📬 Contact

For more information or collaboration inquiries, please contact:
📧 your.email@example.com
🌐 LiberVance
