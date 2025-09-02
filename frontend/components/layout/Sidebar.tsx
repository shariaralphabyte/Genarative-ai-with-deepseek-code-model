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
    loadConversations()
  }, [loadConversations])

  return (
    <div className="w-64 bg-gray-900 text-white flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <Button
          onClick={createNewConversation}
          className="w-full bg-gray-800 hover:bg-gray-700 text-white border border-gray-600"
          variant="outline"
        >
          <PlusIcon className="w-4 h-4 mr-2" />
          New Chat
        </Button>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-2">
          {conversations?.map((conversation) => (
            <div
              key={conversation.id}
              className={`p-3 rounded-lg cursor-pointer hover:bg-gray-800 transition-colors ${
                currentConversation?.id === conversation.id ? 'bg-gray-800' : ''
              }`}
              onClick={() => loadConversation(conversation.id)}
            >
              <div className="flex items-center">
                <MessageSquareIcon className="w-4 h-4 mr-2 text-gray-400" />
                <span className="text-sm truncate">
                  {conversation.title || 'New Conversation'}
                </span>
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {new Date(conversation.updated_at).toLocaleDateString()}
              </div>
            </div>
          ))}
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
