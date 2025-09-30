import { create } from 'zustand'
import axios from 'axios'
import { useAuthStore } from './authStore'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  tokens_used?: number
  inference_time_ms?: number
}

interface Conversation {
  id: string
  title?: string
  messages: Message[]
  created_at: Date
  updated_at: Date
}

interface ChatSettings {
  temperature: number
  maxTokens: number
  systemPrompt: string
}

interface ChatState {
  conversations: Conversation[]
  currentConversation: Conversation | null
  isLoading: boolean
  settings: ChatSettings
  
  // Actions
  sendMessage: (content: string, stream?: boolean) => Promise<void>
  createNewConversation: () => void
  loadConversations: () => Promise<void>
  loadConversation: (id: string) => Promise<void>
  sendFeedback: (messageId: string, type: string, score?: number) => Promise<void>
  updateSettings: (settings: Partial<ChatSettings>) => void
  regenerateResponse: (messageId: string) => Promise<void>
  handleStreamResponse: (content: string) => Promise<void>
  handleRegularResponse: (content: string) => Promise<void>
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentConversation: null,
  isLoading: false,
  settings: {
    temperature: 0.7,
    maxTokens: 4096,
    systemPrompt: 'You are a helpful AI assistant.',
  },

  sendMessage: async (content: string, stream = false) => {
    const { currentConversation, settings } = get()
    
    console.log('SendMessage called with:', content)
    console.log('Current conversation:', currentConversation)
    
    set({ isLoading: true })

    try {
      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content,
        timestamp: new Date(),
      }

      // Add user message to current conversation
      if (currentConversation) {
        console.log('Adding message to existing conversation:', currentConversation.id)
        set({
          currentConversation: {
            ...currentConversation,
            messages: [...currentConversation.messages, userMessage],
          },
        })
      } else {
        // Create new conversation
        console.log('Creating new conversation locally')
        // Get first 5 words for title
        const words = content.trim().split(/\s+/)
        let title = content
        if (words.length > 5) {
          title = words.slice(0, 5).join(' ') + '...'
        } else if (words.length > 0) {
          title = words.join(' ')
        }
        // Fallback to character limit if still too long
        if (title.length > 50) {
          title = title.slice(0, 50) + '...'
        }
        
        const newConversation: Conversation = {
          id: crypto.randomUUID(),
          title: title,
          messages: [userMessage],
          created_at: new Date(),
          updated_at: new Date(),
        }
        console.log('New conversation created:', newConversation)
        set({ currentConversation: newConversation })
      }

      // Always use regular response for now (non-streaming)
      await get().handleRegularResponse(content)
    } catch (error) {
      console.error('Failed to send message:', error)
      
      // Log the actual error for debugging
      if (error instanceof Error) {
        console.error('Error details:', error.message)
        console.error('Error name:', error.name)
      }
      if (axios.isAxiosError(error)) {
        console.error('Response data:', error.response?.data)
        console.error('Response status:', error.response?.status)
        console.error('Request timeout:', error.code === 'ECONNABORTED')
        console.error('Network error:', error.code)
      }
      
      // Add error message to conversation
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Sorry, there was an error processing your message. Please try again.',
        timestamp: new Date(),
      }
      
      const { currentConversation } = get()
      if (currentConversation) {
        set({
          currentConversation: {
            ...currentConversation,
            messages: [...currentConversation.messages, errorMessage],
          },
        })
      }
    } finally {
      set({ isLoading: false })
    }
  },

  handleStreamResponse: async (content: string) => {
    const { currentConversation, settings } = get()
    
    // Get token directly from useAuthStore
    const authState = useAuthStore.getState()
    const token = authState.token
    
    if (!token) {
      throw new Error('No authentication token available')
    }
    
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        conversation_id: currentConversation?.id,
        message: content,
        temperature: settings.temperature,
        max_tokens: settings.maxTokens,
        stream: true,
      }),
    })

    if (!response.ok) {
      throw new Error('Failed to send message')
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('No response body')
    }

    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    }

    // Add empty assistant message
    set({
      currentConversation: currentConversation ? {
        ...currentConversation,
        messages: [...currentConversation.messages, assistantMessage],
      } : null,
    })

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = new TextDecoder().decode(value)
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') {
              return
            }

            try {
              const parsed = JSON.parse(data)
              if (parsed.content) {
                assistantMessage.content += parsed.content
                
                // Update the message in the conversation
                const { currentConversation } = get()
                if (currentConversation) {
                  const updatedMessages = [...currentConversation.messages]
                  const lastMessageIndex = updatedMessages.length - 1
                  updatedMessages[lastMessageIndex] = { ...assistantMessage }
                  
                  set({
                    currentConversation: {
                      ...currentConversation,
                      messages: updatedMessages,
                    },
                  })
                }
              }
            } catch (e) {
              // Ignore parsing errors for malformed chunks
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  },

  handleRegularResponse: async (content: string) => {
    const { currentConversation, settings } = get()
    
    // Get token directly from useAuthStore
    const authState = useAuthStore.getState()
    const token = authState.token
    
    if (!token) {
      throw new Error('No authentication token available')
    }
    
    // Only send conversation_id if it's a real backend conversation (not a locally created one)
    const isLocalConversation = currentConversation && !currentConversation.messages.some(m => m.role === 'assistant')
    const conversationIdToSend = isLocalConversation ? undefined : currentConversation?.id
    
    console.log('Sending conversation_id:', conversationIdToSend, 'isLocalConversation:', isLocalConversation)
    
    const response = await axios.post('/api/chat', {
      conversation_id: conversationIdToSend,
      message: content,
      temperature: settings.temperature,
      max_tokens: settings.maxTokens,
      stream: false,
    }, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      timeout: 10 * 60 * 1000, // 10 minute timeout
    })

    const assistantMessage: Message = {
      id: response.data.id,
      role: 'assistant',
      content: response.data.message,
      timestamp: new Date(),
      tokens_used: response.data.tokens_used,
      inference_time_ms: response.data.inference_time_ms,
    }

    // Update conversation ID if this was a new conversation
    const conversationId = response.data.conversation_id
    console.log('Backend returned conversation ID:', conversationId)
    
    // Add assistant message to conversation
    const { currentConversation: updatedConversation } = get()
    if (updatedConversation) {
      console.log('Updating conversation with backend ID:', conversationId)
      const updatedConv = {
        ...updatedConversation,
        id: conversationId, // Update with backend conversation ID
        messages: [...updatedConversation.messages, assistantMessage],
        updated_at: new Date(),
      }
      
      console.log('Updated conversation:', updatedConv)
      set({ currentConversation: updatedConv })
      
      // Refresh conversations list to include the new/updated conversation
      console.log('Refreshing conversations list...')
      get().loadConversations()
    }
  },

  createNewConversation: () => {
    set({ currentConversation: null })
  },

  loadConversations: async () => {
    try {
      // Get token directly from useAuthStore
      const authState = useAuthStore.getState()
      const token = authState.token
      
      console.log('Loading conversations, token available:', !!token)
      console.log('Current user:', authState.user)
      console.log('Token (first 20 chars):', token?.substring(0, 20) + '...')
      
      if (!token) {
        console.error('No authentication token available for loading conversations')
        return
      }
      
      console.log('Making API call to /api/history...')
      const response = await axios.get('/api/history', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
      
      console.log('Full API response:', response)
      console.log('Response status:', response.status)
      console.log('Response headers:', response.headers)
      
      console.log('API response received:', response.data)
      
      const conversations = (response.data || []).map((conv: any) => ({
        ...conv,
        created_at: new Date(conv.created_at),
        updated_at: new Date(conv.updated_at),
        messages: [], // Messages will be loaded when conversation is selected
      }))
      
      console.log('Processed conversations:', conversations)
      set({ conversations })
    } catch (error) {
      console.error('Failed to load conversations:', error)
      if (axios.isAxiosError(error)) {
        console.error('Response status:', error.response?.status)
        console.error('Response data:', error.response?.data)
      }
      set({ conversations: [] })
    }
  },

  loadConversation: async (id: string) => {
    try {
      // Get token directly from useAuthStore
      const authState = useAuthStore.getState()
      const token = authState.token
      
      if (!token) {
        console.error('No authentication token available for loading conversation')
        return
      }
      
      const response = await axios.get(`/api/conversation/${id}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
      
      const { conversation, messages } = response.data
      
      set({
        currentConversation: {
          ...conversation,
          created_at: new Date(conversation.created_at),
          updated_at: new Date(conversation.updated_at),
          messages: messages.map((msg: any) => ({
            ...msg,
            timestamp: new Date(msg.created_at),
          })),
        },
      })
    } catch (error) {
      console.error('Failed to load conversation:', error)
    }
  },

  sendFeedback: async (messageId: string, type: string, score?: number) => {
    try {
      await axios.post('/api/feedback', {
        message_id: messageId,
        feedback_type: type,
        feedback_score: score,
      })
    } catch (error) {
      console.error('Failed to send feedback:', error)
    }
  },

  regenerateResponse: async (messageId: string) => {
    const { currentConversation } = get()
    if (!currentConversation) return

    // Find the message and get the previous user message
    const messageIndex = currentConversation.messages.findIndex(m => m.id === messageId)
    if (messageIndex <= 0) return

    const userMessage = currentConversation.messages[messageIndex - 1]
    if (userMessage.role !== 'user') return

    // Remove the assistant message and regenerate
    const updatedMessages = currentConversation.messages.slice(0, messageIndex)
    set({
      currentConversation: {
        ...currentConversation,
        messages: updatedMessages,
      },
    })

    await get().sendMessage(userMessage.content)
  },

  updateSettings: (newSettings: Partial<ChatSettings>) => {
    set({
      settings: {
        ...get().settings,
        ...newSettings,
      },
    })
  },
}))
