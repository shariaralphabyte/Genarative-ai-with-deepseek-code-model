package services

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"strings"
	"time"

	"chatgpt-system/internal/llm"
	"chatgpt-system/internal/models"

	"github.com/google/uuid"
)

type ChatService struct {
	db  *sql.DB
	llm *llm.DeepSeekService
}

func NewChatService(db *sql.DB, llmService *llm.DeepSeekService) *ChatService {
	return &ChatService{
		db:  db,
		llm: llmService,
	}
}

func (cs *ChatService) ProcessMessage(ctx context.Context, userID uuid.UUID, req models.ChatRequest) (*models.ChatResponse, error) {
	log.Printf("Processing message for user %s: %s", userID, req.Message)
	// Get or create conversation
	conversationID := req.ConversationID
	isNewConversation := conversationID == nil
	if conversationID == nil {
		newConvID, err := cs.createConversation(ctx, userID, req.SystemPrompt)
		if err != nil {
			return nil, err
		}
		conversationID = &newConvID
	}

	// Store user message
	userMessage := models.Message{
		ID:             uuid.New(),
		ConversationID: *conversationID,
		Role:           "user",
		Content:        req.Message,
		CreatedAt:      time.Now(),
	}

	if err := cs.storeMessage(ctx, userMessage); err != nil {
		return nil, err
	}

	// Set conversation title for new conversations based on first message
	if isNewConversation {
		// Get first 5 words of the message
		words := strings.Fields(req.Message)
		title := req.Message
		if len(words) > 5 {
			title = strings.Join(words[:5], " ") + "..."
		} else if len(words) > 0 {
			title = strings.Join(words, " ")
		}
		// Fallback to character limit if still too long
		if len(title) > 50 {
			title = title[:50] + "..."
		}
		cs.updateConversationTitle(ctx, *conversationID, title)
	}

	// Get conversation history
	messages, err := cs.getConversationMessages(ctx, *conversationID)
	if err != nil {
		return nil, err
	}

	// Generate response from LLM
	log.Printf("Calling LLM service with %d messages", len(messages))
	start := time.Now()
	response, err := cs.llm.GenerateResponse(ctx, messages, &llm.GenerationOptions{
		Temperature:  req.Temperature,
		MaxTokens:    req.MaxTokens,
		SystemPrompt: req.SystemPrompt,
	})
	if err != nil {
		log.Printf("LLM generation failed: %v", err)
		return nil, fmt.Errorf("failed to generate response: %w", err)
	}
	inferenceTime := int(time.Since(start).Milliseconds())
	contentPreview := response.Content
	if len(contentPreview) > 100 {
		contentPreview = contentPreview[:100]
	}
	log.Printf("LLM response received in %dms: %s", inferenceTime, contentPreview)

	// Store assistant message
	response.ID = uuid.New()
	response.ConversationID = *conversationID
	response.CreatedAt = time.Now()
	response.InferenceTimeMs = &inferenceTime

	if err := cs.storeMessage(ctx, *response); err != nil {
		return nil, err
	}

	tokensUsed := 0
	if response.TokensUsed != nil {
		tokensUsed = *response.TokensUsed
	}
	
	modelVersion := "deepseek-ai/deepseek-coder-1.3b-instruct"
	if response.ModelVersion != nil {
		modelVersion = *response.ModelVersion
	}

	return &models.ChatResponse{
		ID:             response.ID,
		ConversationID: *conversationID,
		Message:        response.Content,
		TokensUsed:     tokensUsed,
		InferenceTime:  inferenceTime,
		ModelVersion:   modelVersion,
	}, nil
}

func (cs *ChatService) ProcessStreamMessage(ctx context.Context, userID uuid.UUID, req models.ChatRequest) (<-chan models.StreamChunk, error) {
	// Get or create conversation
	conversationID := req.ConversationID
	if conversationID == nil {
		newConvID, err := cs.createConversation(ctx, userID, req.SystemPrompt)
		if err != nil {
			return nil, err
		}
		conversationID = &newConvID
	}

	// Store user message
	userMessage := models.Message{
		ID:             uuid.New(),
		ConversationID: *conversationID,
		Role:           "user",
		Content:        req.Message,
		CreatedAt:      time.Now(),
	}

	if err := cs.storeMessage(ctx, userMessage); err != nil {
		return nil, err
	}

	// Get conversation history
	messages, err := cs.getConversationMessages(ctx, *conversationID)
	if err != nil {
		return nil, err
	}

	// Generate streaming response
	options := &llm.GenerationOptions{
		Temperature: req.Temperature,
		MaxTokens:   req.MaxTokens,
	}

	chunks, err := cs.llm.GenerateStreamResponse(ctx, messages, options)
	if err != nil {
		return nil, err
	}

	// Process chunks and store final message
	outputChan := make(chan models.StreamChunk, 100)
	go func() {
		defer close(outputChan)
		
		var fullContent string
		messageID := uuid.New()
		
		for chunk := range chunks {
			fullContent += chunk.Content
			
			outputChunk := models.StreamChunk{
				ID:      messageID,
				Content: chunk.Content,
				Done:    chunk.Done,
			}
			
			select {
			case outputChan <- outputChunk:
			case <-ctx.Done():
				return
			}
			
			if chunk.Done {
				// Store complete assistant message
				assistantMessage := models.Message{
					ID:             messageID,
					ConversationID: *conversationID,
					Role:           "assistant",
					Content:        fullContent,
					CreatedAt:      time.Now(),
				}
				cs.storeMessage(ctx, assistantMessage)
				break
			}
		}
	}()

	return outputChan, nil
}

func (cs *ChatService) StoreFeedback(ctx context.Context, userID uuid.UUID, req models.FeedbackRequest) error {
	feedback := models.Feedback{
		ID:           uuid.New(),
		MessageID:    req.MessageID,
		UserID:       userID,
		FeedbackType: req.FeedbackType,
		FeedbackScore: req.FeedbackScore,
		FeedbackText: req.FeedbackText,
		CreatedAt:    time.Now(),
	}

	query := `
		INSERT INTO feedback (id, message_id, user_id, feedback_type, feedback_score, feedback_text, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`

	_, err := cs.db.ExecContext(ctx, query,
		feedback.ID, feedback.MessageID, feedback.UserID,
		feedback.FeedbackType, feedback.FeedbackScore, feedback.FeedbackText,
		feedback.CreatedAt)

	return err
}

func (cs *ChatService) GetUserConversations(ctx context.Context, userID uuid.UUID) ([]models.Conversation, error) {
	query := `
		SELECT id, user_id, title, model_version, system_prompt, created_at, updated_at, is_archived
		FROM conversations
		WHERE user_id = $1 AND is_archived = false
		ORDER BY updated_at DESC`

	rows, err := cs.db.QueryContext(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var conversations []models.Conversation
	for rows.Next() {
		var conv models.Conversation
		err := rows.Scan(&conv.ID, &conv.UserID, &conv.Title, &conv.ModelVersion,
			&conv.SystemPrompt, &conv.CreatedAt, &conv.UpdatedAt, &conv.IsArchived)
		if err != nil {
			return nil, err
		}
		conversations = append(conversations, conv)
	}

	return conversations, nil
}

func (cs *ChatService) GetConversationWithMessages(ctx context.Context, conversationID, userID uuid.UUID) (*models.Conversation, []models.Message, error) {
	// Get conversation
	var conv models.Conversation
	query := `
		SELECT id, user_id, title, model_version, system_prompt, created_at, updated_at, is_archived
		FROM conversations
		WHERE id = $1 AND user_id = $2`

	err := cs.db.QueryRowContext(ctx, query, conversationID, userID).Scan(
		&conv.ID, &conv.UserID, &conv.Title, &conv.ModelVersion,
		&conv.SystemPrompt, &conv.CreatedAt, &conv.UpdatedAt, &conv.IsArchived)
	if err != nil {
		return nil, nil, err
	}

	// Get messages
	messages, err := cs.getConversationMessages(ctx, conversationID)
	if err != nil {
		return nil, nil, err
	}

	return &conv, messages, nil
}

func (cs *ChatService) createConversation(ctx context.Context, userID uuid.UUID, systemPrompt *string) (uuid.UUID, error) {
	conversationID := uuid.New()
	query := `
		INSERT INTO conversations (id, user_id, model_version, system_prompt, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6)`

	_, err := cs.db.ExecContext(ctx, query,
		conversationID, userID, "deepseek-v1.0", systemPrompt, time.Now(), time.Now())

	return conversationID, err
}

func (cs *ChatService) updateConversationTitle(ctx context.Context, conversationID uuid.UUID, title string) error {
	query := `UPDATE conversations SET title = $1, updated_at = $2 WHERE id = $3`
	_, err := cs.db.ExecContext(ctx, query, title, time.Now(), conversationID)
	return err
}

func (cs *ChatService) storeMessage(ctx context.Context, message models.Message) error {
	query := `
		INSERT INTO messages (id, conversation_id, role, content, tokens_used, model_version, inference_time_ms, created_at, metadata)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`

	_, err := cs.db.ExecContext(ctx, query,
		message.ID, message.ConversationID, message.Role, message.Content,
		message.TokensUsed, message.ModelVersion, message.InferenceTimeMs,
		message.CreatedAt, message.Metadata)

	return err
}

func (cs *ChatService) getConversationMessages(ctx context.Context, conversationID uuid.UUID) ([]models.Message, error) {
	query := `
		SELECT id, conversation_id, role, content, tokens_used, model_version, inference_time_ms, created_at, metadata
		FROM messages
		WHERE conversation_id = $1
		ORDER BY created_at ASC`

	rows, err := cs.db.QueryContext(ctx, query, conversationID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var messages []models.Message
	for rows.Next() {
		var msg models.Message
		err := rows.Scan(&msg.ID, &msg.ConversationID, &msg.Role, &msg.Content,
			&msg.TokensUsed, &msg.ModelVersion, &msg.InferenceTimeMs,
			&msg.CreatedAt, &msg.Metadata)
		if err != nil {
			return nil, err
		}
		messages = append(messages, msg)
	}

	return messages, nil
}
