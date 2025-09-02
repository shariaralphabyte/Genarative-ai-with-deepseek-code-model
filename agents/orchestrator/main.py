#!/usr/bin/env python3
"""
AI Agent Orchestrator
Manages and coordinates different AI agents for the ChatGPT system
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

import redis
import psycopg2
from kafka import KafkaProducer, KafkaConsumer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentType(Enum):
    TRAINER = "trainer"
    EVALUATOR = "evaluator"
    DB_MANAGER = "db_manager"
    SUPPORT = "support"

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class AgentTask:
    id: str
    agent_type: AgentType
    task_type: str
    input_data: Dict[str, Any]
    priority: int = 5
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class AgentOrchestrator:
    """Main orchestrator for managing AI agents"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db = self._connect_database()
        self.redis = self._connect_redis()
        self.kafka_producer = self._setup_kafka_producer()
        self.running = False
        
        # Agent queues
        self.task_queues = {
            AgentType.TRAINER: asyncio.Queue(),
            AgentType.EVALUATOR: asyncio.Queue(),
            AgentType.DB_MANAGER: asyncio.Queue(),
            AgentType.SUPPORT: asyncio.Queue(),
        }
        
        # Active agents
        self.active_agents = {}
    
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
        """Connect to Redis"""
        return redis.Redis(
            host=self.config['redis']['host'],
            port=self.config['redis']['port'],
            password=self.config['redis']['password'],
            decode_responses=True
        )
    
    def _setup_kafka_producer(self) -> KafkaProducer:
        """Setup Kafka producer for agent communication"""
        return KafkaProducer(
            bootstrap_servers=self.config['kafka']['brokers'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
    
    async def start(self):
        """Start the orchestrator"""
        logger.info("Starting AI Agent Orchestrator")
        self.running = True
        
        # Start task processors for each agent type
        tasks = []
        for agent_type in AgentType:
            task = asyncio.create_task(self._process_agent_queue(agent_type))
            tasks.append(task)
        
        # Start task scheduler
        scheduler_task = asyncio.create_task(self._schedule_tasks())
        tasks.append(scheduler_task)
        
        # Start health monitor
        monitor_task = asyncio.create_task(self._monitor_agents())
        tasks.append(monitor_task)
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Shutting down orchestrator")
            self.running = False
    
    async def _schedule_tasks(self):
        """Schedule tasks from database to agent queues"""
        while self.running:
            try:
                # Get pending tasks from database
                with self.db.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, agent_type, task_type, input_data, priority, created_at
                        FROM agent_tasks
                        WHERE status = 'pending'
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 50
                    """)
                    
                    tasks = cursor.fetchall()
                    
                    for task_row in tasks:
                        task = AgentTask(
                            id=task_row[0],
                            agent_type=AgentType(task_row[1]),
                            task_type=task_row[2],
                            input_data=json.loads(task_row[3]),
                            priority=task_row[4],
                            created_at=task_row[5]
                        )
                        
                        # Add to appropriate queue
                        await self.task_queues[task.agent_type].put(task)
                        
                        # Update status to running
                        cursor.execute("""
                            UPDATE agent_tasks 
                            SET status = 'running', started_at = %s
                            WHERE id = %s
                        """, (datetime.now(), task.id))
                    
                    self.db.commit()
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in task scheduler: {e}")
                await asyncio.sleep(10)
    
    async def _process_agent_queue(self, agent_type: AgentType):
        """Process tasks for a specific agent type"""
        logger.info(f"Starting {agent_type.value} agent processor")
        
        while self.running:
            try:
                # Get task from queue
                task = await self.task_queues[agent_type].get()
                
                # Process task based on agent type
                if agent_type == AgentType.TRAINER:
                    await self._handle_trainer_task(task)
                elif agent_type == AgentType.EVALUATOR:
                    await self._handle_evaluator_task(task)
                elif agent_type == AgentType.DB_MANAGER:
                    await self._handle_db_manager_task(task)
                elif agent_type == AgentType.SUPPORT:
                    await self._handle_support_task(task)
                
                # Mark task as completed
                self.task_queues[agent_type].task_done()
                
            except Exception as e:
                logger.error(f"Error processing {agent_type.value} task: {e}")
                if 'task' in locals():
                    await self._mark_task_failed(task, str(e))
    
    async def _handle_trainer_task(self, task: AgentTask):
        """Handle training-related tasks"""
        logger.info(f"Processing trainer task: {task.task_type}")
        
        if task.task_type == "start_rlhf_training":
            # Send training request to Kafka
            message = {
                "task_id": task.id,
                "type": "rlhf_training",
                "config": task.input_data
            }
            self.kafka_producer.send('training_requests', message)
            
        elif task.task_type == "evaluate_model":
            # Send evaluation request
            message = {
                "task_id": task.id,
                "type": "model_evaluation",
                "model_path": task.input_data.get("model_path"),
                "eval_dataset": task.input_data.get("eval_dataset")
            }
            self.kafka_producer.send('evaluation_requests', message)
        
        await self._mark_task_completed(task, {"status": "submitted"})
    
    async def _handle_evaluator_task(self, task: AgentTask):
        """Handle evaluation tasks"""
        logger.info(f"Processing evaluator task: {task.task_type}")
        
        if task.task_type == "toxicity_check":
            # Check for toxic content
            content = task.input_data.get("content", "")
            is_toxic = await self._check_toxicity(content)
            
            result = {
                "is_toxic": is_toxic,
                "confidence": 0.95 if is_toxic else 0.05,
                "content_id": task.input_data.get("content_id")
            }
            
        elif task.task_type == "hallucination_detection":
            # Check for hallucinations
            response = task.input_data.get("response", "")
            context = task.input_data.get("context", "")
            
            has_hallucination = await self._detect_hallucination(response, context)
            
            result = {
                "has_hallucination": has_hallucination,
                "confidence": 0.8,
                "response_id": task.input_data.get("response_id")
            }
        
        await self._mark_task_completed(task, result)
    
    async def _handle_db_manager_task(self, task: AgentTask):
        """Handle database management tasks"""
        logger.info(f"Processing DB manager task: {task.task_type}")
        
        if task.task_type == "cleanup_old_conversations":
            # Clean up old conversations
            days_old = task.input_data.get("days_old", 30)
            
            with self.db.cursor() as cursor:
                cursor.execute("""
                    UPDATE conversations 
                    SET is_archived = true 
                    WHERE created_at < NOW() - INTERVAL '%s days'
                    AND is_archived = false
                """, (days_old,))
                
                archived_count = cursor.rowcount
                self.db.commit()
            
            result = {"archived_conversations": archived_count}
            
        elif task.task_type == "backup_feedback_data":
            # Backup feedback data
            backup_path = task.input_data.get("backup_path", "/tmp/feedback_backup.json")
            
            with self.db.cursor() as cursor:
                cursor.execute("""
                    SELECT f.*, m.content as message_content
                    FROM feedback f
                    JOIN messages m ON f.message_id = m.id
                    WHERE f.created_at >= NOW() - INTERVAL '7 days'
                """)
                
                feedback_data = cursor.fetchall()
            
            # Save to file (simplified)
            result = {"backup_path": backup_path, "records_count": len(feedback_data)}
        
        await self._mark_task_completed(task, result)
    
    async def _handle_support_task(self, task: AgentTask):
        """Handle user support tasks"""
        logger.info(f"Processing support task: {task.task_type}")
        
        if task.task_type == "analyze_user_feedback":
            # Analyze user feedback patterns
            user_id = task.input_data.get("user_id")
            
            with self.db.cursor() as cursor:
                cursor.execute("""
                    SELECT feedback_type, AVG(feedback_score), COUNT(*)
                    FROM feedback f
                    JOIN messages m ON f.message_id = m.id
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE c.user_id = %s
                    GROUP BY feedback_type
                """, (user_id,))
                
                feedback_stats = cursor.fetchall()
            
            result = {
                "user_id": user_id,
                "feedback_summary": [
                    {
                        "type": row[0],
                        "avg_score": float(row[1]) if row[1] else 0,
                        "count": row[2]
                    }
                    for row in feedback_stats
                ]
            }
            
        await self._mark_task_completed(task, result)
    
    async def _check_toxicity(self, content: str) -> bool:
        """Simple toxicity check (placeholder)"""
        # In production, use a proper toxicity detection model
        toxic_keywords = ["hate", "toxic", "offensive"]
        return any(keyword in content.lower() for keyword in toxic_keywords)
    
    async def _detect_hallucination(self, response: str, context: str) -> bool:
        """Simple hallucination detection (placeholder)"""
        # In production, use a proper hallucination detection model
        return len(response) > len(context) * 2  # Simple heuristic
    
    async def _mark_task_completed(self, task: AgentTask, output_data: Dict[str, Any]):
        """Mark task as completed in database"""
        with self.db.cursor() as cursor:
            cursor.execute("""
                UPDATE agent_tasks
                SET status = 'completed', completed_at = %s, output_data = %s
                WHERE id = %s
            """, (datetime.now(), json.dumps(output_data), task.id))
            self.db.commit()
        
        logger.info(f"Task {task.id} completed successfully")
    
    async def _mark_task_failed(self, task: AgentTask, error_message: str):
        """Mark task as failed in database"""
        with self.db.cursor() as cursor:
            cursor.execute("""
                UPDATE agent_tasks
                SET status = 'failed', completed_at = %s, error_message = %s
                WHERE id = %s
            """, (datetime.now(), error_message, task.id))
            self.db.commit()
        
        logger.error(f"Task {task.id} failed: {error_message}")
    
    async def _monitor_agents(self):
        """Monitor agent health and performance"""
        while self.running:
            try:
                # Check queue sizes
                for agent_type, queue in self.task_queues.items():
                    queue_size = queue.qsize()
                    
                    # Store metrics in Redis
                    self.redis.setex(
                        f"agent_queue_size:{agent_type.value}",
                        300,  # 5 minutes TTL
                        queue_size
                    )
                    
                    if queue_size > 100:
                        logger.warning(f"{agent_type.value} queue size is high: {queue_size}")
                
                # Check for stuck tasks
                with self.db.cursor() as cursor:
                    cursor.execute("""
                        SELECT COUNT(*) FROM agent_tasks
                        WHERE status = 'running' 
                        AND started_at < NOW() - INTERVAL '1 hour'
                    """)
                    
                    stuck_tasks = cursor.fetchone()[0]
                    if stuck_tasks > 0:
                        logger.warning(f"Found {stuck_tasks} stuck tasks")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in agent monitor: {e}")
                await asyncio.sleep(60)

def create_task(agent_type: str, task_type: str, input_data: Dict[str, Any], priority: int = 5) -> str:
    """Create a new agent task"""
    import uuid
    
    # Connect to database
    db = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        dbname=os.getenv('DB_NAME', 'chatgpt_db'),
        user=os.getenv('DB_USER', 'chatgpt_user'),
        password=os.getenv('DB_PASSWORD', 'chatgpt_password')
    )
    
    task_id = str(uuid.uuid4())
    
    with db.cursor() as cursor:
        cursor.execute("""
            INSERT INTO agent_tasks (id, agent_type, task_type, input_data, priority, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (task_id, agent_type, task_type, json.dumps(input_data), priority, datetime.now()))
        
        db.commit()
    
    db.close()
    return task_id

async def main():
    """Main entry point"""
    import os
    
    config = {
        'database': {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'name': os.getenv('DB_NAME', 'chatgpt_db'),
            'user': os.getenv('DB_USER', 'chatgpt_user'),
            'password': os.getenv('DB_PASSWORD', 'chatgpt_password')
        },
        'redis': {
            'host': os.getenv('REDIS_HOST', 'localhost'),
            'port': os.getenv('REDIS_PORT', '6379'),
            'password': os.getenv('REDIS_PASSWORD', '')
        },
        'kafka': {
            'brokers': os.getenv('KAFKA_BROKERS', 'localhost:9092').split(',')
        }
    }
    
    orchestrator = AgentOrchestrator(config)
    await orchestrator.start()

if __name__ == "__main__":
    asyncio.run(main())
