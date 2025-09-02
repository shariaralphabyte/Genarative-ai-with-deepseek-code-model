package api

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"time"

	"chatgpt-system/internal/config"
	"chatgpt-system/internal/llm"
	"chatgpt-system/internal/models"
	"chatgpt-system/internal/services"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
)

type Handler struct {
	db         *sql.DB
	redis      *redis.Client
	llm        *llm.DeepSeekService
	config     *config.Config
	chatService *services.ChatService
	userService *services.UserService
}

func NewHandler(db *sql.DB, redis *redis.Client, llmService *llm.DeepSeekService, cfg *config.Config) *Handler {
	return &Handler{
		db:          db,
		redis:       redis,
		llm:         llmService,
		config:      cfg,
		chatService: services.NewChatService(db, llmService),
		userService: services.NewUserService(db),
	}
}

// POST /api/chat
func (h *Handler) HandleChat(c *gin.Context) {
	var req models.ChatRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	userID, _ := c.Get("user_id")
	userUUID, err := uuid.Parse(userID.(string))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
		return
	}

	if req.Stream {
		h.handleStreamChat(c, req, userUUID)
		return
	}

	response, err := h.chatService.ProcessMessage(c.Request.Context(), userUUID, req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, response)
}

func (h *Handler) handleStreamChat(c *gin.Context, req models.ChatRequest, userID uuid.UUID) {
	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")

	chunks, err := h.chatService.ProcessStreamMessage(c.Request.Context(), userID, req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	for chunk := range chunks {
		data, _ := json.Marshal(chunk)
		c.SSEvent("data", string(data))
		c.Writer.Flush()

		if chunk.Done {
			break
		}
	}
}

// POST /api/feedback
func (h *Handler) HandleFeedback(c *gin.Context) {
	var req models.FeedbackRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	userID, _ := c.Get("user_id")
	userUUID, err := uuid.Parse(userID.(string))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
		return
	}

	err = h.chatService.StoreFeedback(c.Request.Context(), userUUID, req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Feedback stored successfully"})
}

// GET /api/history
func (h *Handler) HandleHistory(c *gin.Context) {
	userID, _ := c.Get("user_id")
	userUUID, err := uuid.Parse(userID.(string))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
		return
	}

	conversations, err := h.chatService.GetUserConversations(c.Request.Context(), userUUID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, conversations)
}

// GET /api/conversation/:id
func (h *Handler) HandleGetConversation(c *gin.Context) {
	conversationID, err := uuid.Parse(c.Param("id"))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid conversation ID"})
		return
	}

	userID, _ := c.Get("user_id")
	userUUID, err := uuid.Parse(userID.(string))
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid user ID"})
		return
	}

	conversation, messages, err := h.chatService.GetConversationWithMessages(c.Request.Context(), conversationID, userUUID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"conversation": conversation,
		"messages":     messages,
	})
}

// POST /api/train
func (h *Handler) HandleTrain(c *gin.Context) {
	var req models.TrainingRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// TODO: Implement training pipeline
	c.JSON(http.StatusAccepted, gin.H{
		"message": "Training request received",
		"status":  "queued",
	})
}

// POST /api/auth/login
func (h *Handler) HandleLogin(c *gin.Context) {
	var req struct {
		Email    string `json:"email" binding:"required"`
		Password string `json:"password" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	token, user, err := h.userService.Login(c.Request.Context(), req.Email, req.Password, h.config.JWT.Secret, h.config.JWT.Expiry)
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid credentials"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"token": token,
		"user":  user,
	})
}

// POST /api/auth/register
func (h *Handler) HandleRegister(c *gin.Context) {
	var req struct {
		Email    string `json:"email" binding:"required,email"`
		Username string `json:"username" binding:"required,min=3,max=50"`
		Password string `json:"password" binding:"required,min=8"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	user, err := h.userService.Register(c.Request.Context(), req.Email, req.Username, req.Password)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, gin.H{
		"message": "User registered successfully",
		"user":    user,
	})
}

// GET /api/health
func (h *Handler) HandleHealth(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":    "healthy",
		"timestamp": time.Now().Unix(),
		"version":   "1.0.0",
	})
}
