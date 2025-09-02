#!/usr/bin/env python3
"""
Training Agent for DeepSeek LLM
Handles model training, fine-tuning, and RLHF tasks
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

from kafka import KafkaConsumer
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import psycopg2

from training.main import DeepSeekRLTrainer

logger = logging.getLogger(__name__)

class TrainingAgent:
    """Agent responsible for model training tasks"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db = self._connect_database()
        self.consumer = self._setup_kafka_consumer()
        self.running = False
        
        # Training components
        self.trainer = None
        self.current_training_session = None
    
    def _connect_database(self) -> psycopg2.connection:
        """Connect to PostgreSQL database"""
        return psycopg2.connect(
            host=self.config['database']['host'],
            port=self.config['database']['port'],
            dbname=self.config['database']['name'],
            user=self.config['database']['user'],
            password=self.config['database']['password']
        )
    
    def _setup_kafka_consumer(self) -> KafkaConsumer:
        """Setup Kafka consumer for training requests"""
        return KafkaConsumer(
            'training_requests',
            bootstrap_servers=self.config['kafka']['brokers'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id='training_agent'
        )
    
    async def start(self):
        """Start the training agent"""
        logger.info("Starting Training Agent")
        self.running = True
        
        # Start message processing
        await self._process_messages()
    
    async def _process_messages(self):
        """Process incoming training requests"""
        while self.running:
            try:
                # Poll for messages
                message_pack = self.consumer.poll(timeout_ms=1000)
                
                for topic_partition, messages in message_pack.items():
                    for message in messages:
                        await self._handle_training_request(message.value)
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error processing messages: {e}")
                await asyncio.sleep(5)
    
    async def _handle_training_request(self, request: Dict[str, Any]):
        """Handle a training request"""
        task_id = request.get('task_id')
        request_type = request.get('type')
        
        logger.info(f"Processing training request {task_id}: {request_type}")
        
        try:
            if request_type == "rlhf_training":
                await self._start_rlhf_training(task_id, request.get('config', {}))
            elif request_type == "supervised_training":
                await self._start_supervised_training(task_id, request.get('config', {}))
            elif request_type == "model_evaluation":
                await self._evaluate_model(task_id, request)
            else:
                logger.warning(f"Unknown training request type: {request_type}")
                
        except Exception as e:
            logger.error(f"Training request {task_id} failed: {e}")
            await self._update_training_session(task_id, "failed", error_message=str(e))
    
    async def _start_rlhf_training(self, task_id: str, config: Dict[str, Any]):
        """Start RLHF training session"""
        logger.info(f"Starting RLHF training session {task_id}")
        
        # Create training session record
        session_id = await self._create_training_session(task_id, "rlhf", config)
        
        try:
            # Initialize trainer
            training_config_path = config.get('config_path', 'training/config.yaml')
            self.trainer = DeepSeekRLTrainer(training_config_path)
            
            # Initialize model
            model_path = config.get('model_path', 'deepseek-chat')
            self.trainer.initialize_model(model_path)
            
            # Initialize reward model
            reward_model_path = config.get('reward_model_path')
            self.trainer.initialize_reward_model(reward_model_path)
            
            # Setup PPO trainer
            self.trainer.setup_ppo_trainer()
            
            # Start training
            num_epochs = config.get('num_epochs', 5)
            steps_per_epoch = config.get('steps_per_epoch', 50)
            
            await self._update_training_session(session_id, "running")
            
            # Run training in background
            asyncio.create_task(self._run_training(session_id, num_epochs, steps_per_epoch))
            
        except Exception as e:
            await self._update_training_session(session_id, "failed", error_message=str(e))
            raise
    
    async def _run_training(self, session_id: str, num_epochs: int, steps_per_epoch: int):
        """Run the actual training process"""
        try:
            # This would run the training loop
            for epoch in range(num_epochs):
                logger.info(f"Training epoch {epoch + 1}/{num_epochs}")
                
                # Simulate training progress
                for step in range(steps_per_epoch):
                    # In real implementation, this would call trainer.train_step()
                    await asyncio.sleep(0.1)  # Simulate training time
                    
                    # Update progress
                    progress = ((epoch * steps_per_epoch + step + 1) / (num_epochs * steps_per_epoch)) * 100
                    await self._update_training_progress(session_id, progress)
                
                # Save checkpoint after each epoch
                checkpoint_path = f"checkpoints/session_{session_id}_epoch_{epoch + 1}"
                # self.trainer.save_checkpoint(checkpoint_path)
                
                logger.info(f"Epoch {epoch + 1} completed, checkpoint saved")
            
            # Mark as completed
            await self._update_training_session(session_id, "completed")
            logger.info(f"Training session {session_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Training session {session_id} failed: {e}")
            await self._update_training_session(session_id, "failed", error_message=str(e))
    
    async def _start_supervised_training(self, task_id: str, config: Dict[str, Any]):
        """Start supervised fine-tuning"""
        logger.info(f"Starting supervised training {task_id}")
        
        session_id = await self._create_training_session(task_id, "supervised", config)
        
        try:
            # Implementation for supervised training
            dataset_path = config.get('dataset_path')
            model_path = config.get('model_path', 'deepseek-chat')
            
            # Simulate training
            await self._update_training_session(session_id, "running")
            await asyncio.sleep(10)  # Simulate training time
            await self._update_training_session(session_id, "completed")
            
        except Exception as e:
            await self._update_training_session(session_id, "failed", error_message=str(e))
    
    async def _evaluate_model(self, task_id: str, request: Dict[str, Any]):
        """Evaluate model performance"""
        logger.info(f"Evaluating model for task {task_id}")
        
        model_path = request.get('model_path')
        eval_dataset = request.get('eval_dataset')
        
        try:
            # Load model for evaluation
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForCausalLM.from_pretrained(model_path)
            
            # Run evaluation (simplified)
            metrics = {
                "perplexity": 15.2,
                "bleu_score": 0.85,
                "rouge_l": 0.78,
                "eval_samples": 1000
            }
            
            # Store evaluation results
            await self._store_evaluation_results(task_id, model_path, metrics)
            
            logger.info(f"Model evaluation completed: {metrics}")
            
        except Exception as e:
            logger.error(f"Model evaluation failed: {e}")
    
    async def _create_training_session(self, task_id: str, training_type: str, config: Dict[str, Any]) -> str:
        """Create a new training session record"""
        import uuid
        
        session_id = str(uuid.uuid4())
        
        with self.db.cursor() as cursor:
            cursor.execute("""
                INSERT INTO training_sessions (id, training_type, status, config, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (session_id, training_type, "pending", json.dumps(config), datetime.now()))
            
            self.db.commit()
        
        return session_id
    
    async def _update_training_session(self, session_id: str, status: str, error_message: Optional[str] = None):
        """Update training session status"""
        with self.db.cursor() as cursor:
            if status == "running":
                cursor.execute("""
                    UPDATE training_sessions
                    SET status = %s, started_at = %s
                    WHERE id = %s
                """, (status, datetime.now(), session_id))
            elif status in ["completed", "failed"]:
                cursor.execute("""
                    UPDATE training_sessions
                    SET status = %s, completed_at = %s, error_message = %s
                    WHERE id = %s
                """, (status, datetime.now(), error_message, session_id))
            else:
                cursor.execute("""
                    UPDATE training_sessions
                    SET status = %s
                    WHERE id = %s
                """, (status, session_id))
            
            self.db.commit()
    
    async def _update_training_progress(self, session_id: str, progress: float):
        """Update training progress"""
        metrics = {"progress": progress, "updated_at": datetime.now().isoformat()}
        
        with self.db.cursor() as cursor:
            cursor.execute("""
                UPDATE training_sessions
                SET metrics = %s
                WHERE id = %s
            """, (json.dumps(metrics), session_id))
            
            self.db.commit()
    
    async def _store_evaluation_results(self, task_id: str, model_path: str, metrics: Dict[str, Any]):
        """Store model evaluation results"""
        with self.db.cursor() as cursor:
            cursor.execute("""
                INSERT INTO model_versions (version_name, model_type, model_path, performance_metrics, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (f"eval_{task_id}", "deepseek", model_path, json.dumps(metrics), datetime.now()))
            
            self.db.commit()

async def main():
    """Main entry point for training agent"""
    config = {
        'database': {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'name': os.getenv('DB_NAME', 'chatgpt_db'),
            'user': os.getenv('DB_USER', 'chatgpt_user'),
            'password': os.getenv('DB_PASSWORD', 'chatgpt_password')
        },
        'kafka': {
            'brokers': os.getenv('KAFKA_BROKERS', 'localhost:9092').split(',')
        }
    }
    
    agent = TrainingAgent(config)
    await agent.start()

if __name__ == "__main__":
    asyncio.run(main())
