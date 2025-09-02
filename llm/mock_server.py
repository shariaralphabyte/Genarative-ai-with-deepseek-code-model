#!/usr/bin/env python3
"""
Mock LLM server for local testing without requiring actual DeepSeek model
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn
import json
import time
from typing import Dict, Any, List
from pydantic import BaseModel

app = FastAPI(title="Mock DeepSeek LLM Server")

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    model: str = "deepseek-chat"
    choices: List[Dict[str, Any]]

@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": "mock-deepseek"}

@app.get("/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "deepseek-chat",
                "object": "model",
                "created": 1677610602,
                "owned_by": "deepseek"
            }
        ]
    }

@app.post("/chat/completions")
async def chat_completions(request: ChatRequest):
    if request.stream:
        return StreamingResponse(
            generate_stream_response(request),
            media_type="text/plain"
        )
    else:
        return generate_response(request)

def generate_response(request: ChatRequest) -> ChatResponse:
    # Mock response based on the last user message
    last_message = request.messages[-1].content if request.messages else ""
    
    mock_responses = [
        f"I understand you're asking about: {last_message}",
        "This is a mock response from the local DeepSeek server.",
        "In a real deployment, this would be processed by the actual DeepSeek model.",
        f"Your message had {len(last_message)} characters."
    ]
    
    response_text = " ".join(mock_responses)
    
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "model": "deepseek-chat",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response_text
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": len(last_message.split()),
            "completion_tokens": len(response_text.split()),
            "total_tokens": len(last_message.split()) + len(response_text.split())
        }
    }

async def generate_stream_response(request: ChatRequest):
    last_message = request.messages[-1].content if request.messages else ""
    
    mock_words = [
        "I", "understand", "you're", "asking", "about:", f'"{last_message}".', 
        "This", "is", "a", "mock", "streaming", "response", "from", "the", 
        "local", "DeepSeek", "server.", "Each", "word", "is", "streamed", 
        "individually", "to", "simulate", "real", "LLM", "behavior."
    ]
    
    for i, word in enumerate(mock_words):
        chunk = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion.chunk",
            "model": "deepseek-chat",
            "choices": [{
                "index": 0,
                "delta": {"content": word + " "},
                "finish_reason": None
            }]
        }
        
        yield f"data: {json.dumps(chunk)}\n\n"
        time.sleep(0.1)  # Simulate processing time
    
    # Send final chunk
    final_chunk = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion.chunk",
        "model": "deepseek-chat",
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop"
        }]
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
