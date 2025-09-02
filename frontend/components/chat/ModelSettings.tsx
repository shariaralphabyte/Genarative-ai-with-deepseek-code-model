'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useChatStore } from '@/store/chatStore'

export function ModelSettings() {
  const { settings, updateSettings } = useChatStore()
  const [localSettings, setLocalSettings] = useState(settings)

  const handleSave = () => {
    updateSettings(localSettings)
  }

  const handleReset = () => {
    const defaultSettings = {
      temperature: 0.7,
      maxTokens: 4096,
      systemPrompt: 'You are a helpful AI assistant.',
    }
    setLocalSettings(defaultSettings)
    updateSettings(defaultSettings)
  }

  return (
    <div className="p-4 space-y-4">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Model Settings</h3>
      
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Temperature: {localSettings.temperature}
          </label>
          <input
            type="range"
            min="0"
            max="2"
            step="0.1"
            value={localSettings.temperature}
            onChange={(e) => setLocalSettings({
              ...localSettings,
              temperature: parseFloat(e.target.value)
            })}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
          />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>Focused</span>
            <span>Creative</span>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Max Tokens
          </label>
          <Input
            type="number"
            min="1"
            max="8192"
            value={localSettings.maxTokens}
            onChange={(e) => setLocalSettings({
              ...localSettings,
              maxTokens: parseInt(e.target.value) || 4096
            })}
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          System Prompt
        </label>
        <Textarea
          value={localSettings.systemPrompt}
          onChange={(e) => setLocalSettings({
            ...localSettings,
            systemPrompt: e.target.value
          })}
          placeholder="Enter system prompt..."
          className="min-h-[100px]"
        />
      </div>

      <div className="flex space-x-2">
        <Button onClick={handleSave} size="sm">
          Save Settings
        </Button>
        <Button onClick={handleReset} variant="outline" size="sm">
          Reset to Default
        </Button>
      </div>
    </div>
  )
}
