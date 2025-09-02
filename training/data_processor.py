"""
Data processor for handling user feedback and training data
"""

import psycopg2
import redis
import pandas as pd
from datasets import Dataset
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class FeedbackDataProcessor:
    """Process user feedback data for training"""
    
    def __init__(self, db_connection: psycopg2.connection, redis_client: redis.Redis):
        self.db = db_connection
        self.redis = redis_client
    
    def get_feedback_dataset(self, min_feedback_count: int = 10) -> Dataset:
        """Get feedback data for reward model training"""
        query = """
        SELECT 
            m.content as query,
            m2.content as response,
            f.feedback_score,
            f.feedback_type,
            f.feedback_text
        FROM feedback f
        JOIN messages m ON f.message_id = m.id
        JOIN messages m2 ON m2.id = f.message_id
        JOIN conversations c ON m.conversation_id = c.id
        WHERE f.feedback_score IS NOT NULL
        AND m.role = 'user'
        AND m2.role = 'assistant'
        ORDER BY f.created_at DESC
        """
        
        with self.db.cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
            
            if len(results) < min_feedback_count:
                logger.warning(f"Only {len(results)} feedback samples found, minimum {min_feedback_count} recommended")
            
            data = {
                'query': [row[0] for row in results],
                'response': [row[1] for row in results],
                'feedback_score': [row[2] for row in results],
                'feedback_type': [row[3] for row in results],
                'feedback_text': [row[4] for row in results]
            }
            
            return Dataset.from_dict(data)
    
    def get_training_batch(self, batch_size: int = 8) -> List[Dict]:
        """Get a batch of training data for RL"""
        query = """
        SELECT DISTINCT
            m.content as query,
            c.id as conversation_id
        FROM messages m
        JOIN conversations c ON m.conversation_id = c.id
        WHERE m.role = 'user'
        AND EXISTS (
            SELECT 1 FROM feedback f 
            JOIN messages m2 ON f.message_id = m2.id 
            WHERE m2.conversation_id = c.id
        )
        ORDER BY RANDOM()
        LIMIT %s
        """
        
        with self.db.cursor() as cursor:
            cursor.execute(query, (batch_size,))
            results = cursor.fetchall()
            
            return [
                {
                    'query': row[0],
                    'conversation_id': row[1]
                }
                for row in results
            ]
    
    def get_evaluation_dataset(self, limit: int = 100) -> List[Dict]:
        """Get evaluation dataset"""
        query = """
        SELECT 
            m.content as query,
            m2.content as response,
            AVG(f.feedback_score) as avg_score
        FROM messages m
        JOIN messages m2 ON m.conversation_id = m2.conversation_id 
            AND m2.created_at > m.created_at
        JOIN feedback f ON f.message_id = m2.id
        WHERE m.role = 'user' 
        AND m2.role = 'assistant'
        AND f.feedback_score IS NOT NULL
        GROUP BY m.id, m.content, m2.content
        HAVING COUNT(f.id) >= 2
        ORDER BY avg_score DESC
        LIMIT %s
        """
        
        with self.db.cursor() as cursor:
            cursor.execute(query, (limit,))
            results = cursor.fetchall()
            
            return [
                {
                    'query': row[0],
                    'response': row[1],
                    'avg_score': float(row[2])
                }
                for row in results
            ]
    
    def create_preference_pairs(self) -> Dataset:
        """Create preference pairs for pairwise training"""
        query = """
        WITH response_scores AS (
            SELECT 
                m.content as query,
                m2.content as response,
                AVG(f.feedback_score) as avg_score,
                COUNT(f.id) as feedback_count
            FROM messages m
            JOIN messages m2 ON m.conversation_id = m2.conversation_id 
                AND m2.created_at > m.created_at
            JOIN feedback f ON f.message_id = m2.id
            WHERE m.role = 'user' 
            AND m2.role = 'assistant'
            AND f.feedback_score IS NOT NULL
            GROUP BY m.content, m2.content
            HAVING COUNT(f.id) >= 2
        )
        SELECT 
            a.query,
            a.response as response_a,
            b.response as response_b,
            CASE WHEN a.avg_score > b.avg_score THEN 1 ELSE 0 END as preference
        FROM response_scores a
        JOIN response_scores b ON a.query = b.query AND a.response != b.response
        WHERE ABS(a.avg_score - b.avg_score) > 0.2
        """
        
        with self.db.cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
            
            data = {
                'query': [row[0] for row in results],
                'response_a': [row[1] for row in results],
                'response_b': [row[2] for row in results],
                'preference': [row[3] for row in results]
            }
            
            return Dataset.from_dict(data)
    
    def get_conversation_context(self, conversation_id: str, max_messages: int = 10) -> List[Dict]:
        """Get conversation context for training"""
        query = """
        SELECT role, content, created_at
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC
        LIMIT %s
        """
        
        with self.db.cursor() as cursor:
            cursor.execute(query, (conversation_id, max_messages))
            results = cursor.fetchall()
            
            return [
                {
                    'role': row[0],
                    'content': row[1],
                    'timestamp': row[2]
                }
                for row in results
            ]
    
    def cache_training_data(self, dataset: Dataset, cache_key: str, ttl: int = 3600):
        """Cache processed training data in Redis"""
        try:
            data_json = dataset.to_json()
            self.redis.setex(cache_key, ttl, data_json)
            logger.info(f"Cached training data with key: {cache_key}")
        except Exception as e:
            logger.error(f"Failed to cache training data: {e}")
    
    def get_cached_training_data(self, cache_key: str) -> Optional[Dataset]:
        """Get cached training data from Redis"""
        try:
            data_json = self.redis.get(cache_key)
            if data_json:
                return Dataset.from_json(data_json)
        except Exception as e:
            logger.error(f"Failed to get cached training data: {e}")
        
        return None
