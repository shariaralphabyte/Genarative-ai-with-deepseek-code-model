package main

import (
	"log"
	"os"

	"chatgpt-system/internal/api"
	"chatgpt-system/internal/config"
	"chatgpt-system/internal/database"
	"chatgpt-system/internal/llm"
	"chatgpt-system/internal/middleware"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
)

func main() {
	// Load environment variables
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found, using system environment variables")
	}

	// Initialize configuration
	cfg := config.Load()

	// Initialize database
	// Use SQLite for local development
	db, err := database.InitSQLite("./data/chatgpt.db")
	if err != nil {
		log.Fatal("Failed to connect to database:", err)
	}
	defer db.Close()

	// Initialize Redis
	redis := database.InitializeRedis(cfg.Redis)
	defer redis.Close()

	// Initialize LLM service
	llmService := llm.NewDeepSeekService(cfg.LLM)

	// Setup Gin router
	if cfg.Server.Mode == "production" {
		gin.SetMode(gin.ReleaseMode)
	}
	
	router := gin.New()
	router.Use(gin.Logger())
	router.Use(gin.Recovery())
	router.Use(middleware.CORS())

	// Initialize API routes
	apiHandler := api.NewHandler(db, redis, llmService, cfg)
	api.SetupRoutes(router, apiHandler)

	// Start server
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("Server starting on port %s", port)
	if err := router.Run(":" + port); err != nil {
		log.Fatal("Failed to start server:", err)
	}
}
