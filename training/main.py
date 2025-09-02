#!/usr/bin/env python3
"""
Reinforcement Learning Training Pipeline for DeepSeek LLM
Implements RLHF/RLAIF similar to DeepSeek's approach
"""

import os
import json
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from datasets import Dataset
import psycopg2
import redis
import wandb
from trl import PPOTrainer, PPOConfig, AutoModelForCausalLMWithValueHead
from peft import LoraConfig, get_peft_model, TaskType

from reward_model import RewardModel
from data_processor import FeedbackDataProcessor
from utils import setup_logging, load_config

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

class DeepSeekRLTrainer:
    """Main training class for DeepSeek RL pipeline"""
    
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Initialize database connections
        self.db = self._connect_database()
        self.redis = self._connect_redis()
        
        # Initialize model components
        self.tokenizer = None
        self.model = None
        self.reward_model = None
        self.ppo_trainer = None
        
        # Initialize data processor
        self.data_processor = FeedbackDataProcessor(self.db, self.redis)
        
    def _connect_database(self) -> psycopg2.connection:
        """Connect to PostgreSQL database"""
        return psycopg2.connect(
            host=self.config['database']['host'],
            port=self.config['database']['port'],
            dbname=self.config['database']['name'],
            user=self.config['database']['user'],
            password=self.config['database']['password']
        )
    
    def _connect_redis(self) -> redis.Redis:
        """Connect to Redis cache"""
        return redis.Redis(
            host=self.config['redis']['host'],
            port=self.config['redis']['port'],
            password=self.config['redis']['password'],
            decode_responses=True
        )
    
    def initialize_model(self, model_path: str):
        """Initialize DeepSeek model and tokenizer"""
        logger.info(f"Loading model from {model_path}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
        # Load base model
        base_model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True
        )
        
        # Apply LoRA for efficient fine-tuning
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=16,
            lora_alpha=32,
            lora_dropout=0.1,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj"]
        )
        
        self.model = get_peft_model(base_model, lora_config)
        
        # Wrap model for PPO training
        self.model = AutoModelForCausalLMWithValueHead.from_pretrained(
            self.model,
            torch_dtype=torch.float16
        )
        
        logger.info("Model initialized successfully")
    
    def initialize_reward_model(self, reward_model_path: Optional[str] = None):
        """Initialize or train reward model from user feedback"""
        if reward_model_path and os.path.exists(reward_model_path):
            logger.info(f"Loading existing reward model from {reward_model_path}")
            self.reward_model = RewardModel.load(reward_model_path)
        else:
            logger.info("Training new reward model from feedback data")
            feedback_data = self.data_processor.get_feedback_dataset()
            
            self.reward_model = RewardModel(
                model_name=self.config['reward_model']['base_model'],
                device=self.device
            )
            
            self.reward_model.train(feedback_data)
            
            # Save trained reward model
            save_path = f"checkpoints/reward_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.reward_model.save(save_path)
            logger.info(f"Reward model saved to {save_path}")
    
    def setup_ppo_trainer(self):
        """Setup PPO trainer for reinforcement learning"""
        ppo_config = PPOConfig(
            model_name=self.config['training']['model_name'],
            learning_rate=self.config['training']['learning_rate'],
            batch_size=self.config['training']['batch_size'],
            mini_batch_size=self.config['training']['mini_batch_size'],
            gradient_accumulation_steps=self.config['training']['gradient_accumulation_steps'],
            optimize_cuda_cache=True,
            early_stopping=True,
            target_kl=0.1,
            ppo_epochs=4,
            seed=42,
        )
        
        self.ppo_trainer = PPOTrainer(
            config=ppo_config,
            model=self.model,
            ref_model=None,
            tokenizer=self.tokenizer,
        )
        
        logger.info("PPO trainer initialized")
    
    def train_step(self, batch_size: int = 8) -> Dict[str, float]:
        """Execute one training step with PPO"""
        # Get training data from database
        training_data = self.data_processor.get_training_batch(batch_size)
        
        if not training_data:
            logger.warning("No training data available")
            return {}
        
        queries = [item['query'] for item in training_data]
        query_tensors = [self.tokenizer.encode(query, return_tensors="pt")[0] for query in queries]
        
        # Generate responses
        response_tensors = []
        for query_tensor in query_tensors:
            response = self.ppo_trainer.generate(
                query_tensor.unsqueeze(0),
                max_length=self.config['training']['max_response_length'],
                do_sample=True,
                temperature=0.7,
                pad_token_id=self.tokenizer.pad_token_id
            )
            response_tensors.append(response[0])
        
        # Get rewards from reward model
        rewards = []
        for query, response_tensor in zip(queries, response_tensors):
            response_text = self.tokenizer.decode(response_tensor, skip_special_tokens=True)
            reward = self.reward_model.get_reward(query, response_text)
            rewards.append(torch.tensor(reward))
        
        # PPO training step
        stats = self.ppo_trainer.step(query_tensors, response_tensors, rewards)
        
        # Log metrics
        if wandb.run:
            wandb.log(stats)
        
        return stats
    
    def train(self, num_epochs: int = 10, steps_per_epoch: int = 100):
        """Main training loop"""
        logger.info(f"Starting training for {num_epochs} epochs")
        
        # Initialize wandb
        if self.config.get('wandb', {}).get('enabled', False):
            wandb.init(
                project=self.config['wandb']['project'],
                config=self.config
            )
        
        for epoch in range(num_epochs):
            logger.info(f"Starting epoch {epoch + 1}/{num_epochs}")
            
            epoch_stats = []
            for step in range(steps_per_epoch):
                try:
                    stats = self.train_step()
                    epoch_stats.append(stats)
                    
                    if step % 10 == 0:
                        logger.info(f"Epoch {epoch + 1}, Step {step + 1}: {stats}")
                        
                except Exception as e:
                    logger.error(f"Training step failed: {e}")
                    continue
            
            # Save checkpoint
            checkpoint_path = f"checkpoints/deepseek_rl_epoch_{epoch + 1}"
            self.save_checkpoint(checkpoint_path)
            
            # Evaluate model
            eval_metrics = self.evaluate()
            logger.info(f"Epoch {epoch + 1} evaluation: {eval_metrics}")
            
            if wandb.run:
                wandb.log({"epoch": epoch + 1, **eval_metrics})
        
        logger.info("Training completed")
    
    def evaluate(self) -> Dict[str, float]:
        """Evaluate model performance"""
        eval_data = self.data_processor.get_evaluation_dataset()
        
        total_reward = 0
        num_samples = 0
        
        for item in eval_data[:50]:  # Evaluate on subset
            query = item['query']
            query_tensor = self.tokenizer.encode(query, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                response = self.model.generate(
                    query_tensor,
                    max_length=512,
                    do_sample=True,
                    temperature=0.7,
                    pad_token_id=self.tokenizer.pad_token_id
                )
            
            response_text = self.tokenizer.decode(response[0], skip_special_tokens=True)
            reward = self.reward_model.get_reward(query, response_text)
            
            total_reward += reward
            num_samples += 1
        
        avg_reward = total_reward / num_samples if num_samples > 0 else 0
        
        return {
            "avg_reward": avg_reward,
            "num_eval_samples": num_samples
        }
    
    def save_checkpoint(self, path: str):
        """Save model checkpoint"""
        os.makedirs(path, exist_ok=True)
        
        self.model.save_pretrained(path)
        self.tokenizer.save_pretrained(path)
        
        # Save training metadata
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "config": self.config,
            "model_type": "deepseek-rl"
        }
        
        with open(f"{path}/metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Checkpoint saved to {path}")

def main():
    parser = argparse.ArgumentParser(description="DeepSeek RL Training Pipeline")
    parser.add_argument("--config", required=True, help="Path to config file")
    parser.add_argument("--model-path", required=True, help="Path to base DeepSeek model")
    parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs")
    parser.add_argument("--steps-per-epoch", type=int, default=100, help="Steps per epoch")
    
    args = parser.parse_args()
    
    # Initialize trainer
    trainer = DeepSeekRLTrainer(args.config)
    
    # Initialize model and reward model
    trainer.initialize_model(args.model_path)
    trainer.initialize_reward_model()
    trainer.setup_ppo_trainer()
    
    # Start training
    trainer.train(args.epochs, args.steps_per_epoch)

if __name__ == "__main__":
    main()
