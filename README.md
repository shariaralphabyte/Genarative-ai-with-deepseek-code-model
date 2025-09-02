# ChatGPT-like System with DeepSeek LLM

A full-stack chatbot system featuring custom DeepSeek LLM integration, real-time chat interface, and production-ready deployment.

## 🏗️ Architecture

```
├── backend/                 # Go API server with JWT auth
├── frontend/               # Next.js + TailwindCSS ChatGPT-style UI
├── llm/                    # DeepSeek 1.3B model server
├── training/               # RL training pipeline (optional)
├── agents/                 # AI agent orchestration (optional)
├── database/               # SQLite database & schemas
├── deployment/             # Docker & Kubernetes configs
└── scripts/                # Utility scripts
```

## 🚀 Quick Start

### Prerequisites
- **Go** 1.19+
- **Node.js** 18+
- **Python** 3.9+
- **Redis** (for caching)

### 1. Clone and Setup
```bash
git clone <repository-url>
cd Re
```

### 2. Start Redis
```bash
# macOS with Homebrew
brew install redis
redis-server --daemonize yes --port 6379

# Or use Docker
docker run -d -p 6379:6379 redis:alpine
```

### 3. Backend Setup
```bash
cd backend
cp .env.example .env
go mod download
go run main.go
```
**Backend runs on:** http://localhost:8080

### 4. LLM Server Setup
```bash
cd llm
pip install -r requirements.txt
python3 server.py
```
**LLM Server runs on:** http://localhost:8000

### 5. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
**Frontend runs on:** http://localhost:3000

### 6. One-Command Start (Alternative)
```bash
chmod +x start-local.sh
./start-local.sh
```

## 🎯 Usage

1. **Open** http://localhost:3000
2. **Register** a new account or login
3. **Start chatting** with the DeepSeek AI model
4. **Get responses** in 30-60 seconds

## 📋 Features

- 🤖 **DeepSeek 1.3B Coder Model** - Local AI inference
- 💬 **ChatGPT-style Interface** - Real-time streaming chat
- 🔐 **JWT Authentication** - Secure user sessions
- 💾 **Conversation History** - Persistent chat storage
- 🎨 **Modern UI** - TailwindCSS + shadcn/ui components
- ⚡ **Fast Response** - Optimized for 30-60s inference
- 🔄 **Auto-retry** - 10-minute timeout handling

## 🛠️ Configuration

### Backend Environment (.env)
```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=chatgpt_db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# JWT
JWT_SECRET=your-super-secret-jwt-key
JWT_EXPIRY=24h

# LLM
DEEPSEEK_API_URL=http://localhost:8000
DEEPSEEK_MAX_TOKENS=4096
DEEPSEEK_TEMPERATURE=0.7

# Server
PORT=8080
GIN_MODE=debug
```

### LLM Model Configuration
- **Model**: deepseek-ai/deepseek-coder-1.3b-instruct
- **Device**: CPU (auto-detects GPU if available)
- **Max Tokens**: 512 (configurable)
- **Temperature**: 0.7 (configurable)

## 🔧 Troubleshooting

### Common Issues

**1. Backend won't start - Port 8080 in use**
```bash
lsof -ti:8080 | xargs kill -9
```

**2. LLM server timeout/hanging**
```bash
# Restart LLM server
pkill -f "python3 server.py"
cd llm && python3 server.py
```

**3. Frontend can't connect to backend**
- Check backend is running on port 8080
- Verify Next.js proxy configuration in `next.config.js`

**4. Redis connection failed**
```bash
# Start Redis
redis-server --daemonize yes --port 6379
```

**5. Model loading errors**
```bash
# Install missing dependencies
cd llm
pip install torch transformers fastapi uvicorn
```

### Performance Tips

- **CPU Usage**: DeepSeek model uses significant CPU for inference
- **Memory**: Requires ~4GB RAM for model loading
- **Response Time**: 30-60 seconds normal for CPU inference
- **Timeout**: Set to 10 minutes to handle longer responses

## 📁 Project Structure

```
backend/
├── internal/
│   ├── api/           # HTTP handlers
│   ├── config/        # Configuration
│   ├── database/      # DB connection
│   ├── llm/          # LLM service
│   ├── middleware/    # JWT, CORS, etc.
│   ├── models/       # Data models
│   └── services/     # Business logic
└── main.go           # Entry point

frontend/
├── app/              # Next.js app router
├── components/       # React components
├── hooks/           # Custom hooks
├── lib/             # Utilities
└── store/           # Zustand state management

llm/
├── server.py        # FastAPI LLM server
├── requirements.txt # Python dependencies
└── mock_server.py   # Testing mock server
```

## 🚢 Deployment

### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up -d
```

### Kubernetes Deployment
```bash
# Apply Kubernetes manifests
kubectl apply -f deployment/kubernetes/
```

### Production Checklist
- [ ] Set strong JWT secret
- [ ] Configure PostgreSQL for production
- [ ] Set up SSL/TLS certificates
- [ ] Configure reverse proxy (nginx)
- [ ] Set up monitoring and logging
- [ ] Configure auto-scaling for LLM server

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
