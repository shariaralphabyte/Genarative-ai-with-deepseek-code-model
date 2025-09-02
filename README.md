# ChatGPT-like System with DeepSeek LLM

A full-stack chatbot system featuring custom DeepSeek LLM integration, reinforcement learning training, and ChatGPT-style UI.

## Architecture

```
├── backend/                 # Go API server
├── frontend/               # Next.js + TailwindCSS UI
├── llm/                    # DeepSeek LLM integration
├── training/               # RL training pipeline
├── agents/                 # AI agent orchestration
├── database/               # PostgreSQL schemas & migrations
├── deployment/             # Docker & cloud configs
├── scripts/                # Utility scripts
└── docs/                   # Documentation
```

## Quick Start

1. **Database Setup**
   ```bash
   cd database && docker-compose up -d
   ```

2. **Backend**
   ```bash
   cd backend && go run main.go
   ```

3. **Frontend**
   ```bash
   cd frontend && npm run dev
   ```

4. **Training Pipeline**
   ```bash
   cd training && python main.py
   ```

## Features

- 🤖 Custom DeepSeek LLM integration
- 💬 ChatGPT-style streaming chat interface
- 🧠 Reinforcement learning with user feedback
- 🔄 AI agent orchestration system
- 📊 Real-time model performance monitoring
- 🚀 Production-ready deployment
