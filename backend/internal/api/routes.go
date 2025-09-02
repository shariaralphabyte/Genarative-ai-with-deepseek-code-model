package api

import (
	"chatgpt-system/internal/middleware"

	"github.com/gin-gonic/gin"
)

func SetupRoutes(router *gin.Engine, handler *Handler) {
	// Public routes
	public := router.Group("/api")
	{
		public.POST("/auth/login", handler.HandleLogin)
		public.POST("/auth/register", handler.HandleRegister)
		public.GET("/health", handler.HandleHealth)
	}

	// Protected routes
	protected := router.Group("/api")
	protected.Use(middleware.AuthMiddleware(handler.config.JWT.Secret))
	protected.Use(middleware.RateLimitMiddleware(
		handler.redis,
		handler.config.RateLimit.RequestsPerMinute,
		handler.config.RateLimit.Burst,
	))
	{
		protected.POST("/chat", handler.HandleChat)
		protected.POST("/feedback", handler.HandleFeedback)
		protected.GET("/history", handler.HandleHistory)
		protected.GET("/conversation/:id", handler.HandleGetConversation)
		protected.POST("/train", handler.HandleTrain)
	}
}
