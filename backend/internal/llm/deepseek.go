package llm

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"chatgpt-system/internal/config"
	"chatgpt-system/internal/models"
)

type DeepSeekService struct {
	config    config.LLMConfig
	client    *http.Client
	modelPath string
}

type DeepSeekRequest struct {
	Messages    []ChatMessage `json:"messages"`
	MaxTokens   int          `json:"max_tokens"`
	Temperature float64      `json:"temperature"`
	Stream      bool         `json:"stream"`
	Model       string       `json:"model"`
}

type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type DeepSeekResponse struct {
	ID      string `json:"id"`
	Object  string `json:"object"`
	Created int64  `json:"created"`
	Model   string `json:"model"`
	Choices []struct {
		Index   int `json:"index"`
		Message struct {
			Role    string `json:"role"`
			Content string `json:"content"`
		} `json:"message"`
		Delta struct {
			Content string `json:"content"`
		} `json:"delta"`
		FinishReason *string `json:"finish_reason"`
	} `json:"choices"`
	Usage struct {
		PromptTokens     int `json:"prompt_tokens"`
		CompletionTokens int `json:"completion_tokens"`
		TotalTokens      int `json:"total_tokens"`
	} `json:"usage"`
}

func NewDeepSeekService(config config.LLMConfig) *DeepSeekService {
	return &DeepSeekService{
		config: config,
		client: &http.Client{
			Timeout: 10 * time.Minute, // Set 10 minute timeout
		},
		modelPath: config.ModelPath,
	}
}

func (ds *DeepSeekService) GenerateResponse(ctx context.Context, messages []models.Message, options *GenerationOptions) (*models.Message, error) {
	chatMessages := make([]ChatMessage, len(messages))
	for i, msg := range messages {
		chatMessages[i] = ChatMessage{
			Role:    msg.Role,
			Content: msg.Content,
		}
	}

	temperature := ds.config.Temperature
	maxTokens := ds.config.MaxTokens

	if options != nil {
		if options.Temperature != nil {
			temperature = *options.Temperature
		}
		if options.MaxTokens != nil {
			maxTokens = *options.MaxTokens
		}
	}

	request := DeepSeekRequest{
		Messages:    chatMessages,
		MaxTokens:   maxTokens,
		Temperature: temperature,
		Stream:      false,
		Model:       "deepseek-chat",
	}

	response, err := ds.makeRequest(ctx, request)
	if err != nil {
		return nil, err
	}

	if len(response.Choices) == 0 {
		return nil, fmt.Errorf("no response choices returned")
	}

	tokensUsed := 0
	if response.Usage.TotalTokens > 0 {
		tokensUsed = response.Usage.TotalTokens
	}
	
	modelVersion := "deepseek-ai/deepseek-coder-1.3b-instruct"
	if response.Model != "" {
		modelVersion = response.Model
	}

	result := &models.Message{
		Role:         "assistant",
		Content:      response.Choices[0].Message.Content,
		TokensUsed:   &tokensUsed,
		ModelVersion: &modelVersion,
	}

	return result, nil
}

func (ds *DeepSeekService) GenerateStreamResponse(ctx context.Context, messages []models.Message, options *GenerationOptions) (<-chan models.StreamChunk, error) {
	chatMessages := make([]ChatMessage, len(messages))
	for i, msg := range messages {
		chatMessages[i] = ChatMessage{
			Role:    msg.Role,
			Content: msg.Content,
		}
	}

	temperature := ds.config.Temperature
	maxTokens := ds.config.MaxTokens

	if options != nil {
		if options.Temperature != nil {
			temperature = *options.Temperature
		}
		if options.MaxTokens != nil {
			maxTokens = *options.MaxTokens
		}
	}

	request := DeepSeekRequest{
		Messages:    chatMessages,
		MaxTokens:   maxTokens,
		Temperature: temperature,
		Stream:      true,
		Model:       "deepseek-chat",
	}

	return ds.makeStreamRequest(ctx, request)
}

func (ds *DeepSeekService) makeRequest(ctx context.Context, request DeepSeekRequest) (*DeepSeekResponse, error) {
	jsonData, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Create request without context to avoid timeout cancellation
	req, err := http.NewRequest("POST", ds.config.APIUrl+"/chat/completions", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := ds.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API request failed with status %d: %s", resp.StatusCode, string(body))
	}

	var response DeepSeekResponse
	if err := json.NewDecoder(resp.Body).Decode(&response); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &response, nil
}

func (ds *DeepSeekService) makeStreamRequest(ctx context.Context, request DeepSeekRequest) (<-chan models.StreamChunk, error) {
	jsonData, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", ds.config.APIUrl+"/chat/completions", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "text/event-stream")

	resp, err := ds.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to make request: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		return nil, fmt.Errorf("API request failed with status %d: %s", resp.StatusCode, string(body))
	}

	chunks := make(chan models.StreamChunk, 100)

	go func() {
		defer resp.Body.Close()
		defer close(chunks)

		scanner := bufio.NewScanner(resp.Body)
		for scanner.Scan() {
			line := scanner.Text()
			if line == "" || !bytes.HasPrefix([]byte(line), []byte("data: ")) {
				continue
			}

			data := line[6:] // Remove "data: " prefix
			if data == "[DONE]" {
				chunks <- models.StreamChunk{Done: true}
				return
			}

			var response DeepSeekResponse
			if err := json.Unmarshal([]byte(data), &response); err != nil {
				continue
			}

			if len(response.Choices) > 0 {
				chunk := models.StreamChunk{
					Content: response.Choices[0].Delta.Content,
					Done:    response.Choices[0].FinishReason != nil,
				}
				
				select {
				case chunks <- chunk:
				case <-ctx.Done():
					return
				}
			}
		}
	}()

	return chunks, nil
}

type GenerationOptions struct {
	Temperature *float64
	MaxTokens   *int
	SystemPrompt *string
}
