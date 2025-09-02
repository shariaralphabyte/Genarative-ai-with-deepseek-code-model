package models

import (
	"time"

	"github.com/google/uuid"
)

type User struct {
	ID               uuid.UUID  `json:"id" db:"id"`
	Email            string     `json:"email" db:"email"`
	Username         string     `json:"username" db:"username"`
	PasswordHash     string     `json:"-" db:"password_hash"`
	APIKey           *string    `json:"api_key,omitempty" db:"api_key"`
	SubscriptionTier string     `json:"subscription_tier" db:"subscription_tier"`
	CreatedAt        time.Time  `json:"created_at" db:"created_at"`
	UpdatedAt        time.Time  `json:"updated_at" db:"updated_at"`
	LastLogin        *time.Time `json:"last_login,omitempty" db:"last_login"`
	IsActive         bool       `json:"is_active" db:"is_active"`
}

type Conversation struct {
	ID           uuid.UUID `json:"id" db:"id"`
	UserID       uuid.UUID `json:"user_id" db:"user_id"`
	Title        *string   `json:"title,omitempty" db:"title"`
	ModelVersion string    `json:"model_version" db:"model_version"`
	SystemPrompt *string   `json:"system_prompt,omitempty" db:"system_prompt"`
	CreatedAt    time.Time `json:"created_at" db:"created_at"`
	UpdatedAt    time.Time `json:"updated_at" db:"updated_at"`
	IsArchived   bool      `json:"is_archived" db:"is_archived"`
}

type Message struct {
	ID             uuid.UUID   `json:"id" db:"id"`
	ConversationID uuid.UUID   `json:"conversation_id" db:"conversation_id"`
	Role           string      `json:"role" db:"role"`
	Content        string      `json:"content" db:"content"`
	TokensUsed     *int        `json:"tokens_used,omitempty" db:"tokens_used"`
	ModelVersion   *string     `json:"model_version,omitempty" db:"model_version"`
	InferenceTimeMs *int       `json:"inference_time_ms,omitempty" db:"inference_time_ms"`
	CreatedAt      time.Time   `json:"created_at" db:"created_at"`
	Metadata       interface{} `json:"metadata,omitempty" db:"metadata"`
}

type Feedback struct {
	ID           uuid.UUID  `json:"id" db:"id"`
	MessageID    uuid.UUID  `json:"message_id" db:"message_id"`
	UserID       uuid.UUID  `json:"user_id" db:"user_id"`
	FeedbackType string     `json:"feedback_type" db:"feedback_type"`
	FeedbackScore *float64  `json:"feedback_score,omitempty" db:"feedback_score"`
	FeedbackText *string    `json:"feedback_text,omitempty" db:"feedback_text"`
	CreatedAt    time.Time  `json:"created_at" db:"created_at"`
}

type ModelVersion struct {
	ID                 uuid.UUID   `json:"id" db:"id"`
	VersionName        string      `json:"version_name" db:"version_name"`
	ModelType          string      `json:"model_type" db:"model_type"`
	ModelPath          *string     `json:"model_path,omitempty" db:"model_path"`
	Config             interface{} `json:"config" db:"config"`
	PerformanceMetrics interface{} `json:"performance_metrics,omitempty" db:"performance_metrics"`
	IsActive           bool        `json:"is_active" db:"is_active"`
	CreatedAt          time.Time   `json:"created_at" db:"created_at"`
	UpdatedAt          time.Time   `json:"updated_at" db:"updated_at"`
}

type ChatRequest struct {
	ConversationID *uuid.UUID `json:"conversation_id,omitempty"`
	Message        string     `json:"message" binding:"required"`
	SystemPrompt   *string    `json:"system_prompt,omitempty"`
	Temperature    *float64   `json:"temperature,omitempty"`
	MaxTokens      *int       `json:"max_tokens,omitempty"`
	Stream         bool       `json:"stream"`
}

type ChatResponse struct {
	ID             uuid.UUID `json:"id"`
	ConversationID uuid.UUID `json:"conversation_id"`
	Message        string    `json:"message"`
	TokensUsed     int       `json:"tokens_used"`
	InferenceTime  int       `json:"inference_time_ms"`
	ModelVersion   string    `json:"model_version"`
}

type StreamChunk struct {
	ID      uuid.UUID `json:"id"`
	Content string    `json:"content"`
	Done    bool      `json:"done"`
}

type FeedbackRequest struct {
	MessageID     uuid.UUID `json:"message_id" binding:"required"`
	FeedbackType  string    `json:"feedback_type" binding:"required"`
	FeedbackScore *float64  `json:"feedback_score,omitempty"`
	FeedbackText  *string   `json:"feedback_text,omitempty"`
}

type TrainingRequest struct {
	ModelVersionID uuid.UUID   `json:"model_version_id" binding:"required"`
	TrainingType   string      `json:"training_type" binding:"required"`
	Config         interface{} `json:"config" binding:"required"`
}
