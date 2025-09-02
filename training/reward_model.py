"""
Reward Model for RLHF Training
Based on user feedback data to score model responses
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel, Trainer, TrainingArguments
from datasets import Dataset
import numpy as np
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class RewardModel(nn.Module):
    """Reward model for scoring LLM responses based on human feedback"""
    
    def __init__(self, model_name: str = "microsoft/DialoGPT-medium", device: str = "cuda"):
        super().__init__()
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.backbone = AutoModel.from_pretrained(model_name)
        
        # Add reward head
        self.reward_head = nn.Sequential(
            nn.Linear(self.backbone.config.hidden_size, 512),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(512, 1)
        )
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
    
    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """Forward pass through reward model"""
        outputs = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        
        # Use last hidden state for reward prediction
        last_hidden_state = outputs.last_hidden_state
        
        # Pool over sequence length (mean pooling)
        pooled = torch.mean(last_hidden_state, dim=1)
        
        # Get reward score
        reward = self.reward_head(pooled)
        return reward.squeeze(-1)
    
    def get_reward(self, query: str, response: str) -> float:
        """Get reward score for a query-response pair"""
        # Combine query and response
        text = f"Query: {query}\nResponse: {response}"
        
        # Tokenize
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512
        ).to(self.device)
        
        # Get reward
        with torch.no_grad():
            reward = self.forward(inputs['input_ids'], inputs['attention_mask'])
            return reward.item()
    
    def train(self, feedback_dataset: Dataset, output_dir: str = "reward_model_checkpoints"):
        """Train reward model on feedback data"""
        logger.info("Starting reward model training")
        
        def preprocess_function(examples):
            """Preprocess feedback data for training"""
            texts = []
            labels = []
            
            for i in range(len(examples['query'])):
                query = examples['query'][i]
                response = examples['response'][i]
                score = examples['feedback_score'][i]
                
                text = f"Query: {query}\nResponse: {response}"
                texts.append(text)
                labels.append(score)
            
            # Tokenize
            tokenized = self.tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt"
            )
            
            tokenized['labels'] = torch.tensor(labels, dtype=torch.float)
            return tokenized
        
        # Preprocess dataset
        train_dataset = feedback_dataset.map(
            preprocess_function,
            batched=True,
            remove_columns=feedback_dataset.column_names
        )
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=3,
            per_device_train_batch_size=8,
            per_device_eval_batch_size=8,
            warmup_steps=100,
            weight_decay=0.01,
            logging_dir=f"{output_dir}/logs",
            logging_steps=10,
            save_steps=500,
            evaluation_strategy="steps",
            eval_steps=500,
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
        )
        
        # Custom trainer for reward model
        trainer = RewardModelTrainer(
            model=self,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=train_dataset.train_test_split(test_size=0.2)['test'],
            tokenizer=self.tokenizer,
        )
        
        # Train
        trainer.train()
        
        # Save final model
        trainer.save_model()
        logger.info(f"Reward model training completed. Model saved to {output_dir}")
    
    def save(self, path: str):
        """Save reward model"""
        torch.save({
            'model_state_dict': self.state_dict(),
            'tokenizer': self.tokenizer,
            'config': self.backbone.config,
        }, f"{path}/reward_model.pt")
    
    @classmethod
    def load(cls, path: str):
        """Load reward model from checkpoint"""
        checkpoint = torch.load(f"{path}/reward_model.pt")
        
        model = cls()
        model.load_state_dict(checkpoint['model_state_dict'])
        model.tokenizer = checkpoint['tokenizer']
        
        return model

class RewardModelTrainer(Trainer):
    """Custom trainer for reward model"""
    
    def compute_loss(self, model, inputs, return_outputs=False):
        """Compute MSE loss for reward prediction"""
        labels = inputs.pop("labels")
        
        # Forward pass
        outputs = model(**inputs)
        
        # MSE loss
        loss = F.mse_loss(outputs, labels)
        
        return (loss, outputs) if return_outputs else loss

class PairwiseRewardModel(RewardModel):
    """Pairwise reward model for ranking responses"""
    
    def __init__(self, model_name: str = "microsoft/DialoGPT-medium", device: str = "cuda"):
        super().__init__(model_name, device)
        
        # Override reward head for pairwise comparison
        self.reward_head = nn.Sequential(
            nn.Linear(self.backbone.config.hidden_size * 2, 512),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(512, 1),
            nn.Sigmoid()
        )
    
    def forward_pair(self, query: str, response_a: str, response_b: str) -> torch.Tensor:
        """Compare two responses for the same query"""
        # Encode both responses
        text_a = f"Query: {query}\nResponse: {response_a}"
        text_b = f"Query: {query}\nResponse: {response_b}"
        
        inputs_a = self.tokenizer(text_a, return_tensors="pt", padding=True, truncation=True, max_length=512).to(self.device)
        inputs_b = self.tokenizer(text_b, return_tensors="pt", padding=True, truncation=True, max_length=512).to(self.device)
        
        # Get embeddings
        with torch.no_grad():
            outputs_a = self.backbone(**inputs_a)
            outputs_b = self.backbone(**inputs_b)
            
            pooled_a = torch.mean(outputs_a.last_hidden_state, dim=1)
            pooled_b = torch.mean(outputs_b.last_hidden_state, dim=1)
        
        # Concatenate embeddings
        combined = torch.cat([pooled_a, pooled_b], dim=-1)
        
        # Get preference probability (A preferred over B)
        preference = self.reward_head(combined)
        return preference.squeeze(-1)
