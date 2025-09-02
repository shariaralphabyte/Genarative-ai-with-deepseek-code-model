#!/usr/bin/env python3
"""
DeepSeek LLM Server with GPU acceleration and streaming support
"""

import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn
import json
import asyncio
from threading import Thread
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import psutil
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="DeepSeek LLM Server", version="1.0.0")

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False

class DeepSeekServer:
    def __init__(self, model_name: str = "deepseek-ai/deepseek-coder-1.3b-instruct"):
        self.model_name = model_name
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.tokenizer = None
        
        logger.info(f"Initializing DeepSeek server with model: {model_name}")
        logger.info(f"Using device: {self.device}")
        
        self.load_model()
    
    def load_model(self):
        """Load the DeepSeek model and tokenizer"""
        try:
            logger.info("Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )
            
            # Add padding token if it doesn't exist
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            logger.info("Loading model...")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None,
                trust_remote_code=True,
                low_cpu_mem_usage=True
            )
            
            if not torch.cuda.is_available():
                self.model = self.model.to(self.device)
            
            logger.info("Model loaded successfully!")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise HTTPException(status_code=500, detail=f"Model loading failed: {str(e)}")
    
    def format_messages(self, messages: List[ChatMessage]) -> str:
        """Format messages for DeepSeek model"""
        formatted = ""
        for msg in messages:
            if msg.role == "system":
                formatted += f"{msg.content}\n\n"
            elif msg.role == "user":
                formatted += f"### Instruction:\n{msg.content}\n\n"
            elif msg.role == "assistant":
                formatted += f"### Response:\n{msg.content}\n\n"
        
        formatted += "### Response:\n"
        return formatted
    
    async def generate_response(self, request: ChatRequest) -> Dict[str, Any]:
        """Generate a complete response"""
        try:
            prompt = self.format_messages(request.messages)
            formatted_prompt = prompt
            inputs = self.tokenizer.encode(formatted_prompt, return_tensors="pt").to(self.device)
        
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs,
                    max_new_tokens=min(request.max_tokens, 512),  
                    temperature=request.temperature,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                    repetition_penalty=1.1,
                    early_stopping=True,  
                    top_p=0.9,
                )
            
            # Decode only the new tokens
            response_tokens = outputs[0][inputs.shape[1]:]
            response_text = self.tokenizer.decode(response_tokens, skip_special_tokens=True)
            
            return {
                "id": f"chatcmpl-{int(datetime.now().timestamp())}",
                "object": "chat.completion",
                "model": self.model_name,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text.strip()
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": inputs.shape[1],
                    "completion_tokens": len(response_tokens),
                    "total_tokens": inputs.shape[1] + len(response_tokens)
                }
            }
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def generate_stream_response(self, request: ChatRequest):
        """Generate a streaming response"""
        try:
            prompt = self.format_messages(request.messages)
            
            inputs = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
            
            streamer = TextIteratorStreamer(
                self.tokenizer,
                timeout=60.0,
                skip_prompt=True,
                skip_special_tokens=True
            )
            
            generation_kwargs = {
                "input_ids": inputs,
                "max_new_tokens": min(request.max_tokens, 512),
                "temperature": request.temperature,
                "do_sample": True,
                "pad_token_id": self.tokenizer.pad_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
                "repetition_penalty": 1.1,
                "top_p": 0.9,
                "streamer": streamer,
            }
            
            # Start generation in a separate thread
            thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
            thread.start()
            
            # Stream the response
            for new_text in streamer:
                chunk = {
                    "id": f"chatcmpl-{int(datetime.now().timestamp())}",
                    "object": "chat.completion.chunk",
                    "model": self.model_name,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": new_text},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.01)
            
            # Send final chunk
            final_chunk = {
                "id": f"chatcmpl-{int(datetime.now().timestamp())}",
                "object": "chat.completion.chunk",
                "model": self.model_name,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            error_chunk = {
                "error": {
                    "message": str(e),
                    "type": "generation_error"
                }
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"

# Initialize the server
server = DeepSeekServer()

@app.post("/chat/completions")
async def chat_completions(request: ChatRequest):
    """Chat completions endpoint compatible with OpenAI API"""
    try:
        if request.stream:
            return StreamingResponse(
                server.generate_stream_response(request),
                media_type="text/event-stream"
            )
        else:
            response = await server.generate_response(request)
            return response
            
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    gpu_available = torch.cuda.is_available()
    gpu_count = torch.cuda.device_count() if gpu_available else 0
    
    memory_info = psutil.virtual_memory()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "model_loaded": server.model is not None,
        "device": str(server.device),
        "gpu_available": gpu_available,
        "gpu_count": gpu_count,
        "memory_usage": {
            "total": memory_info.total,
            "available": memory_info.available,
            "percent": memory_info.percent
        }
    }

@app.get("/models")
async def list_models():
    """List available models"""
    return {
        "object": "list",
        "data": [{
            "id": server.model_name,
            "object": "model",
            "created": int(datetime.now().timestamp()),
            "owned_by": "deepseek"
        }]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
