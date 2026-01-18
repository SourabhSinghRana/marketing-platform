import random
import json
import os
import time
import logging
import sqlite3
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from pymongo import MongoClient
from neo4j import GraphDatabase
from pymilvus import (
    connections,
    FieldSchema, CollectionSchema, DataType,
    Collection, utility
)

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("ETL_Pipeline")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:password@localhost:27017/")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_AUTH = (NEO4J_USER, NEO4J_PASSWORD)

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")

SQLITE_DB = "analytics.db"

# Gemini Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable not set.")
    raise ValueError("GEMINI_API_KEY missing")

genai.configure(api_key=GEMINI_API_KEY)

# Milvus Config
COLLECTION_NAME = "user_embeddings"
DIMENSION = 768

def get_embedding(text):
    """
    Generates vector using Gemini API.
    Includes Retry Logic and a Fallback to ensure the pipeline finishes 
    even if the API Rate Limit is hit.
    """
    retries = 1
    for attempt in range(retries):
        try:
            # Increase sleep to 2 seconds to stay under the limit (~30 req/min)
            time.sleep(2.0) 
            
            result = genai.embed_content(
                model="models/embedding-001",
                content=text,
                task_type="retrieval_document",
                title="Marketing Chat"
            )
            return result['embedding']
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                # Calculate wait time: 10s, 20s, 30s
                wait_time = (attempt + 1) * 10
                logger.warning(f"Rate limit (429) hit. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Non-retryable error: {e}")
                break 

    # --- FALLBACK ---
    # If API fails after retries, return a random vector so the pipeline doesn't crash.
    logger.error(f"Could not embed text: '{text[:20]}...'. Using DUMMY vector.")
    return [random.uniform(-0.1, 0.1) for _ in range(DIMENSION)]

# --- Database Setup ---

def setup_mongo():
    try:
        client = MongoClient(MONGO_URI)
        db = client["marketing_platform"]
        # Ping to check connection
        client.admin.command('ping')
        logger.info("Connected to MongoDB.")
        return db
    except Exception as e:
        logger.critical(f"Failed to connect to MongoDB: {e}")
        raise

def setup_neo4j():
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
        driver.verify_connectivity()
        logger.info("Connected to Neo4j.")
        return driver
    except Exception as e:
        logger.critical(f"Failed to connect to Neo4j: {e}")
        raise

def setup_milvus():
    try:
        connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
        
        if utility.has_collection(COLLECTION_NAME):
            utility.drop_collection(COLLECTION_NAME)
            logger.info(f"Dropped existing Milvus collection: {COLLECTION_NAME}")

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="interaction_id", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=DIMENSION)
        ]
        schema = CollectionSchema(fields, "User conversation embeddings")
        collection = Collection(COLLECTION_NAME, schema)
        
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        collection.create_index(field_name="vector", index_params=index_params)
        collection.load()
        logger.info("Milvus collection created and loaded.")
        return collection
    except Exception as e:
        logger.critical(f"Failed to connect to Milvus: {e}")
        raise

def setup_sqlite():
    try:
        conn = sqlite3.connect(SQLITE_DB)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaign_analytics (
                campaign_id TEXT PRIMARY KEY,
                total_interactions INTEGER,
                last_updated TIMESTAMP
            )
        """)
        conn.commit()
        logger.info("SQLite analytics table initialized.")
        return conn
    except Exception as e:
        logger.critical(f"Failed to initialize SQLite: {e}")
        raise

# --- Main Pipeline Logic ---

def run_pipeline():
    start_time = time.time()
    logger.info("Pipeline execution started.")

    try:
        # 1. Load Data
        logger.info("Loading JSON data...")
        with open("data/users.json") as f: users = json.load(f)
        with open("data/campaigns.json") as f: campaigns = json.load(f)
        with open("data/interactions.json") as f: interactions = json.load(f)
        
        # 2. Connect DBs
        mongo_db = setup_mongo()
        neo4j_driver = setup_neo4j()
        milvus_col = setup_milvus()
        sqlite_conn = setup_sqlite()
        
        # 3. Process Users & Campaigns (Neo4j)
        logger.info("Syncing Users and Campaigns to Neo4j...")
        with neo4j_driver.session() as session:
            for u in users:
                session.run(
                    "MERGE (u:User {user_id: $uid}) SET u.name = $name",
                    uid=u['user_id'], name=u['name']
                )
            for c in campaigns:
                session.run(
                    "MERGE (c:Campaign {campaign_id: $cid}) SET c.name = $name",
                    cid=c['campaign_id'], name=c['name']
                )

        # 4. Process Interactions
        logger.info(f"Processing {len(interactions)} interactions...")
        
        milvus_data = {
            "user_id": [],
            "interaction_id": [],
            "vector": []
        }
        
        mongo_docs = []
        analytics_counter = {}
        processed_count = 0

        with neo4j_driver.session() as session:
            for idx, item in enumerate(interactions):
                # A. Prepare Mongo Document
                mongo_docs.append(item)
                
                # B. Prepare Neo4j Relationship
                session.run("""
                    MATCH (u:User {user_id: $uid})
                    MATCH (c:Campaign {campaign_id: $cid})
                    MERGE (u)-[:INTERACTED {type: $type, timestamp: $ts}]->(c)
                """, uid=item['user_id'], cid=item['campaign_id'], 
                    type=item['type'], ts=item['timestamp'])

                # C. Vector Processing (Only for chats)
                if item['type'] == 'chat' and 'message' in item:
                    vector = get_embedding(item['message'])
                    milvus_data["user_id"].append(item['user_id'])
                    milvus_data["interaction_id"].append(item['interaction_id'])
                    milvus_data["vector"].append(vector)
                    
                # D. Analytics Aggregation
                cid = item['campaign_id']
                analytics_counter[cid] = analytics_counter.get(cid, 0) + 1
                
                processed_count += 1
                if processed_count % 20 == 0:
                    logger.info(f"Processed {processed_count}/{len(interactions)} records...")

        # 5. Bulk Insert to MongoDB
        if mongo_docs:
            mongo_db.interactions.insert_many(mongo_docs)
            logger.info(f"Inserted {len(mongo_docs)} docs to MongoDB.")

        # 6. Bulk Insert to Milvus
        if milvus_data["vector"]:
            milvus_col.insert([
                milvus_data["user_id"],
                milvus_data["interaction_id"],
                milvus_data["vector"]
            ])
            logger.info(f"Inserted {len(milvus_data['vector'])} vectors to Milvus.")

        # 7. Update Analytics (SQLite)
        cursor = sqlite_conn.cursor()
        for cid, count in analytics_counter.items():
            cursor.execute("""
                INSERT INTO campaign_analytics (campaign_id, total_interactions, last_updated)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(campaign_id) DO UPDATE SET
                total_interactions = total_interactions + ?
            """, (cid, count, count))
        sqlite_conn.commit()
        logger.info("Analytics updated in SQLite.")

        # Cleanup
        neo4j_driver.close()
        sqlite_conn.close()
        
        duration = time.time() - start_time
        logger.info(f"Pipeline finished successfully in {duration:.2f} seconds.")

    except Exception as e:
        logger.error(f"Pipeline crashed: {e}")
        raise

if __name__ == "__main__":
    run_pipeline()