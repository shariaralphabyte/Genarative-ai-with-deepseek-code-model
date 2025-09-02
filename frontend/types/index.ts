export interface User {
  id: string
  email: string
  username: string
  subscription_tier: string
  created_at: string
  updated_at: string
  last_login?: string
  is_active: boolean
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  tokens_used?: number
  model_version?: string
  inference_time_ms?: number
  created_at: string
  metadata?: any
}

export interface Conversation {
  id: string
  user_id: string
  title?: string
  model_version: string
  system_prompt?: string
  created_at: string
  updated_at: string
  is_archived: boolean
}

export interface ChatRequest {
  conversation_id?: string
  message: string
  system_prompt?: string
  temperature?: number
  max_tokens?: number
  stream: boolean
}

export interface ChatResponse {
  id: string
  conversation_id: string
  message: string
  tokens_used: number
  inference_time: number
  model_version: string
}

export interface StreamChunk {
  id: string
  content: string
  done: boolean
}

export interface FeedbackRequest {
  message_id: string
  feedback_type: string
  feedback_score?: number
  feedback_text?: string
}
