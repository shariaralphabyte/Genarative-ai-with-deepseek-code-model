'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { useChatStore } from '@/store/chatStore'
import { useAuthStore } from '@/store/authStore'
import { PlusIcon, MessageSquareIcon, SettingsIcon, LogOutIcon } from 'lucide-react'

export function Sidebar() {
  const { 
    conversations, 
    currentConversation, 
    createNewConversation, 
    loadConversations, 
    loadConversation 
  } = useChatStore()
  const { user, logout } = useAuthStore()

  useEffect(() => {
    console.log('Sidebar mounted, loading conversations...')
    loadConversations()
  }, [loadConversations])

  useEffect(() => {
    console.log('Conversations updated:', conversations)
  }, [conversations])

  return (
    <div className="w-64 bg-gray-900 text-white flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-700 space-y-2">
        <Button
          onClick={createNewConversation}
          className="w-full bg-gray-800 hover:bg-gray-700 text-white border border-gray-600"
          variant="outline"
        >
          <PlusIcon className="w-4 h-4 mr-2" />
          New Chat
        </Button>
        <Button
          onClick={() => {
            console.log('Manual refresh clicked')
            loadConversations()
          }}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white text-xs"
          size="sm"
        >
          🔄 Refresh History
        </Button>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-2">
          {conversations?.length === 0 ? (
            <div className="text-center text-gray-400 text-sm mt-8">
              <MessageSquareIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No conversations yet</p>
              <p className="text-xs mt-1">Start a new chat to begin</p>
            </div>
          ) : (
            conversations?.map((conversation) => (
              <div
                key={conversation.id}
                className={`p-3 rounded-lg cursor-pointer hover:bg-gray-800 transition-colors ${
                  currentConversation?.id === conversation.id ? 'bg-gray-800 border-l-2 border-blue-500' : ''
                }`}
                onClick={() => loadConversation(conversation.id)}
              >
                <div className="flex items-center">
                  <MessageSquareIcon className="w-4 h-4 mr-2 text-gray-400 flex-shrink-0" />
                  <span className="text-sm truncate">
                    {conversation.title || 'New Conversation'}
                  </span>
                </div>
                <div className="text-xs text-gray-400 mt-1 ml-6">
                  {new Date(conversation.updated_at).toLocaleDateString()}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
              <span className="text-sm font-medium">
                {user?.username?.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="text-sm">
              <div className="font-medium">{user?.username}</div>
              <div className="text-gray-400 text-xs">{user?.subscription_tier}</div>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={logout}
            className="text-gray-400 hover:text-white"
          >
            <LogOutIcon className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
