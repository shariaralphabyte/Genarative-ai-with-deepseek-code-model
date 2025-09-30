'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { useChatStore } from '@/store/chatStore'
import { ThumbsUpIcon, ThumbsDownIcon, RefreshCwIcon, CopyIcon } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  tokens_used?: number
  inference_time_ms?: number
}

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false)
  const { sendFeedback, regenerateResponse } = useChatStore()

  const formatResponseTime = (timeMs: number) => {
    if (timeMs >= 60000) {
      const minutes = Math.floor(timeMs / 60000)
      const seconds = Math.floor((timeMs % 60000) / 1000)
      return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`
    } else if (timeMs >= 1000) {
      const seconds = Math.floor(timeMs / 1000)
      return `${seconds}s`
    } else {
      return `${timeMs}ms`
    }
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleFeedback = async (type: 'thumbs_up' | 'thumbs_down') => {
    const score = type === 'thumbs_up' ? 1.0 : -1.0
    await sendFeedback(message.id, type, score)
  }

  const handleRegenerate = async () => {
    await regenerateResponse(message.id)
  }

  const isUser = message.role === 'user'
  const isAssistant = message.role === 'assistant'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-[85%] min-w-0 ${isUser ? 'order-2' : 'order-1'}`} style={{ maxWidth: '85vw' }}>
        {/* Avatar */}
        <div className={`flex items-start space-x-3 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}>
          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
            isUser 
              ? 'bg-blue-600 text-white' 
              : 'bg-green-600 text-white'
          }`}>
            {isUser ? 'U' : 'AI'}
          </div>
          
          <div className={`rounded-lg p-4 min-w-0 ${
            isUser 
              ? 'bg-blue-600 text-white' 
              : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white'
          }`}>
            {/* Message Content */}
            <div className="prose prose-sm max-w-none dark:prose-invert">
              {isUser ? (
                <p className="whitespace-pre-wrap">{message.content}</p>
              ) : (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={{
                    code({ node, inline, className, children, ...props }: any) {
                      const match = /language-(\w+)/.exec(className || '')
                      return !inline && match ? (
                        <div className="relative group max-w-full">
                          <div className="code-container">
                            <SyntaxHighlighter
                              style={oneDark}
                              language={match[1]}
                              PreTag="div"
                              customStyle={{
                                margin: 0,
                                borderRadius: '0.375rem',
                                fontSize: '0.875rem',
                                paddingRight: '3rem',
                                maxWidth: '100%',
                                overflow: 'auto',
                              }}
                            codeTagProps={{
                              style: {
                                fontSize: '0.875rem',
                                fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace',
                              },
                            }}
                            {...props}
                          >
                            {String(children).replace(/\n$/, '')}
                            </SyntaxHighlighter>
                          </div>
                          <button
                            onClick={() => navigator.clipboard.writeText(String(children).replace(/\n$/, ''))}
                            className="absolute top-2 right-2 p-1.5 bg-gray-700 hover:bg-gray-600 rounded text-gray-300 hover:text-white opacity-0 group-hover:opacity-100 transition-opacity"
                            title="Copy code"
                          >
                            <CopyIcon className="w-3 h-3" />
                          </button>
                        </div>
                      ) : (
                        <code className={`${className} bg-gray-200 dark:bg-gray-700 px-1 py-0.5 rounded text-sm font-mono`} {...props}>
                          {children}
                        </code>
                      )
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              )}
            </div>

            {/* Message Actions */}
            {isAssistant && (
              <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-200 dark:border-gray-600">
                <div className="flex items-center space-x-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleFeedback('thumbs_up')}
                    className="h-8 w-8 p-0"
                  >
                    <ThumbsUpIcon className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleFeedback('thumbs_down')}
                    className="h-8 w-8 p-0"
                  >
                    <ThumbsDownIcon className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleRegenerate}
                    className="h-8 w-8 p-0"
                  >
                    <RefreshCwIcon className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCopy}
                    className="h-8 w-8 p-0"
                  >
                    <CopyIcon className="w-4 h-4" />
                  </Button>
                </div>
                
                {/* Message Stats */}
                <div className="text-xs text-gray-500 space-x-2">
                  {message.tokens_used && (
                    <span>{message.tokens_used} tokens</span>
                  )}
                  {message.inference_time_ms && (
                    <span>{formatResponseTime(message.inference_time_ms)}</span>
                  )}
                </div>
              </div>
            )}

            {/* Copy Success */}
            {copied && (
              <div className="text-xs text-green-600 mt-1">Copied to clipboard!</div>
            )}
          </div>
        </div>

        {/* Timestamp */}
        <div className={`text-xs text-gray-500 mt-1 ${isUser ? 'text-right' : 'text-left'} ml-11`}>
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  )
}
