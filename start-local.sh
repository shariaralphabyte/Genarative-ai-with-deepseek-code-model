#!/bin/bash

# Start local ChatGPT system
echo "Starting ChatGPT System locally..."

# Create data directory
mkdir -p backend/data

# Start Redis
echo "Starting Redis..."
redis-server --daemonize yes --port 6379

# Start backend
echo "Starting backend API..."
cd backend
go run main.go &
BACKEND_PID=$!
cd ..

# Start frontend
echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo "System started!"
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8080"
echo ""
echo "To stop the system, run: kill $BACKEND_PID $FRONTEND_PID"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"

# Wait for user input to stop
read -p "Press Enter to stop all services..."
kill $BACKEND_PID $FRONTEND_PID
redis-cli shutdown
echo "All services stopped."
